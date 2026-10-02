from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .config import ROOT
from .run_status import read_run_status
from .skill_center import skill_catalog, run_skill
from .store import list_activity
from .application_tracker import ApplicationTracker, STATUSES, TRANSITIONS
from .job_preferences import DEFAULT_JOB_PREFERENCES


# One worker prevents two Playwright sessions from competing for the same
# persistent LinkedIn profile. The HTTP server itself remains responsive.
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="linkedin-dashboard")
_TASKS: dict[str, dict] = {}
_TASK_LOCK = threading.Lock()
_MAX_TASKS = 100
_MAX_REQUEST_BODY_BYTES = 1_048_576


def _task_submit(kind: str, fn) -> str:
    task_id = uuid.uuid4().hex[:12]
    with _TASK_LOCK:
        if len(_TASKS) >= _MAX_TASKS:
            finished = [k for k, v in _TASKS.items() if v.get("status") in {"completed", "failed"}]
            for k in finished[: max(1, len(finished) // 2)]:
                _TASKS.pop(k, None)
        _TASKS[task_id] = {"id": task_id, "kind": kind, "status": "queued"}

    def worker():
        with _TASK_LOCK:
            _TASKS[task_id]["status"] = "running"
        try:
            result = fn()
            with _TASK_LOCK:
                _TASKS[task_id].update(status="completed", result=result)
        except Exception as exc:
            with _TASK_LOCK:
                _TASKS[task_id].update(
                    status="failed",
                    error=f"{type(exc).__name__}: {exc}",
                )

    _EXECUTOR.submit(worker)
    return task_id


def _has_active_task(kind: str) -> bool:
    with _TASK_LOCK:
        return any(
            item.get("kind") == kind and item.get("status") in {"queued", "running"}
            for item in _TASKS.values()
        )


def _parse_approval_decision(value) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError("approved must be a boolean")


def _read_json_body(handler) -> dict:
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except (TypeError, ValueError):
        raise ValueError("Invalid Content-Length")
    if length < 0 or length > _MAX_REQUEST_BODY_BYTES:
        raise ValueError("Request body is too large")
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    return payload


def _task_get(task_id: str) -> dict | None:
    with _TASK_LOCK:
        item = _TASKS.get(task_id)
        return dict(item) if item else None


def _db(path: str):
    # Dashboard reads must never wait behind an agent write for seconds. SQLite
    # returns a controlled OperationalError on contention; _safe_section then
    # renders the affected panel with a warning instead of hanging the API.
    con = sqlite3.connect(path, timeout=0.5)
    con.execute("PRAGMA busy_timeout=500")
    con.row_factory = sqlite3.Row
    return con


def _safe_section(name: str, fn, default, warnings: list[str]):
    try:
        return fn()
    except Exception as exc:
        warnings.append(f"{name}: {type(exc).__name__}: {exc}")
        return default


def _summary() -> dict:
    warnings: list[str] = []
    activity = str(ROOT / "data" / "activity.sqlite3")

    def load_approvals():
        with _db(activity) as db:
            rows = db.execute(
                "SELECT id,action,target,payload,status,created_at FROM approval_queue "
                "WHERE status='pending' ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
            return [dict(r) for r in rows]

    def load_applications():
        with _db(activity) as db:
            count = db.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
            columns = {row[1] for row in db.execute("PRAGMA table_info(applications)").fetchall()}
            wanted = [
                "job_url", "title", "company", "status", "updated_at", "notes",
                "discovered_at", "applied_at", "source", "location", "recruiter",
                "resume_version", "next_follow_up", "interview_date", "salary_notes",
            ]
            if all(column in columns for column in wanted):
                rows = db.execute(
                    "SELECT " + ",".join(wanted) +
                    " FROM applications ORDER BY updated_at DESC LIMIT 50"
                ).fetchall()
            else:
                # Backward-compatible read path for test fixtures or an older
                # activity database that has not yet been migrated.
                rows = db.execute(
                    "SELECT job_url,title,company,status,updated_at,notes "
                    "FROM applications ORDER BY updated_at DESC LIMIT 50"
                ).fetchall()
            out = []
            for r in rows:
                item = dict(r)
                for key in wanted:
                    item.setdefault(key, "")
                item["allowed_transitions"] = sorted(
                    TRANSITIONS.get(item["status"], set())
                )
                out.append(item)
            return count, out

    def load_jobs():
        # This endpoint is read-only. Do not run History() migrations here because
        # they acquire a write lock and can make /api/summary appear to hang while
        # the scheduled agent is writing the shared SQLite database.
        with _db(activity) as db:
            freshness_hours = float(DEFAULT_JOB_PREFERENCES.posted_within_hours)
            cutoff = datetime.now(timezone.utc) - timedelta(hours=freshness_hours)
            raw_rows = db.execute(
                "SELECT id,title,company,location,url,score,reasons,status,first_seen,"
                "posted_hours,posted_text,posted_at "
                "FROM job_history ORDER BY id DESC LIMIT 1000"
            ).fetchall()

            def _parse_dt(value):
                try:
                    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    return parsed.astimezone(timezone.utc)
                except (TypeError, ValueError):
                    return None

            rows = []
            for row in raw_rows:
                posted_at = _parse_dt(row["posted_at"])
                if posted_at is None:
                    # Legacy rows may have only a captured numeric age. Reconstruct
                    # the approximate posting timestamp from first_seen rather than
                    # treating the stored age as if it were still current.
                    first_seen = _parse_dt(row["first_seen"])
                    try:
                        age = float(row["posted_hours"]) if row["posted_hours"] is not None else None
                    except (TypeError, ValueError):
                        age = None
                    if first_seen is not None and age is not None and age >= 0:
                        posted_at = first_seen - timedelta(hours=age)
                if posted_at is None or posted_at < cutoff:
                    continue
                rows.append(row)

            count = len(rows)
            out = []
            for r in rows[:50]:
                location = str(r["location"] or "")
                context = f"{location} {r['reasons'] or ''}".lower()
                if "remote" in context:
                    workplace_type = "remote"
                elif "hybrid" in context:
                    workplace_type = "hybrid"
                elif "on-site" in context or "onsite" in context:
                    workplace_type = "on-site"
                else:
                    workplace_type = ""
                out.append(
                    {
                        "title": r["title"],
                        "company": r["company"],
                        "location": r["location"],
                        "url": r["url"],
                        "score": r["score"],
                        "reasons": r["reasons"],
                        "status": r["status"],
                        "workplace_type": workplace_type,
                        "posted": r["posted_text"] or "",
                        "posted_hours": r["posted_hours"],
                        "updated_at": r["first_seen"],
                    }
                )
            return count, out

    approvals = _safe_section("approvals", load_approvals, [], warnings)
    application_data = _safe_section("applications", load_applications, (0, []), warnings)
    job_data = _safe_section("jobs", load_jobs, (0, []), warnings)
    last_run = _safe_section("last_run", read_run_status, {}, warnings)

    return {
        "activity": _safe_section(
            "activity",
            lambda: [
                {
                    "created_at": row[0],
                    "action": row[1],
                    "target": row[2],
                    "status": row[3],
                    "details": row[4],
                }
                for row in list_activity(limit=30)
            ],
            [],
            warnings,
        ),
        "jobs_tracked": job_data[0],
        "application_count": application_data[0],
        "pending_approvals": len(approvals),
        "recent_jobs": len(job_data[1]),
        "approvals": approvals,
        "applications": application_data[1],
        "jobs": job_data[1],
        "last_run": last_run,
        "warnings": warnings,
    }


_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LinkedIn Agent — Control Center</title>
<style>
:root{
 --bg:#07111f;--bg2:#0b1728;--panel:rgba(16,28,46,.82);--panel2:rgba(20,36,58,.9);
 --ink:#edf5ff;--muted:#9bb0c8;--line:rgba(154,181,211,.16);
 --blue:#48a8ff;--blue2:#177ddc;--green:#32d583;--amber:#fdb022;--red:#f97066;
 --nav:#050d18;--nav2:rgba(72,168,255,.13);--shadow:0 18px 55px rgba(0,0,0,.28)
}
*{box-sizing:border-box}html{background:var(--bg)}body{margin:0;font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;color:var(--ink);background:
 radial-gradient(circle at 15% 5%,rgba(72,168,255,.12),transparent 28rem),
 radial-gradient(circle at 85% 20%,rgba(84,104,255,.09),transparent 32rem),
 linear-gradient(145deg,var(--bg),var(--bg2));min-height:100vh}
button,input,textarea,select{font:inherit}button{border:0;cursor:pointer}
.app{display:flex;min-height:100vh}.sidebar{width:248px;background:linear-gradient(180deg,rgba(5,13,24,.97),rgba(7,17,31,.94));border-right:1px solid var(--line);color:#fff;padding:20px 14px;position:fixed;inset:0 auto 0 0;z-index:5;backdrop-filter:blur(18px)}
.brand{display:flex;gap:10px;align-items:center;padding:4px 8px 22px}.brand-mark{width:36px;height:36px;border-radius:11px;background:linear-gradient(145deg,#5fc0ff,#126bc1);display:grid;place-items:center;font-weight:900;box-shadow:0 8px 25px rgba(72,168,255,.25);transform:perspective(80px) rotateX(3deg)}
.brand strong{display:block;font-size:15px}.brand span{display:block;color:#8198b2;font-size:11px}
.nav{display:grid;gap:5px}.nav button{background:transparent;color:#9db1c8;text-align:left;padding:11px 12px;border:1px solid transparent;border-radius:10px;width:100%;font-weight:650;transition:.18s ease;box-shadow:none}
.nav button:hover,.nav button.active{background:var(--nav2);border-color:rgba(72,168,255,.16);color:#fff;transform:translateX(2px);box-shadow:inset 0 1px rgba(255,255,255,.04),0 8px 22px rgba(0,0,0,.12)}
.nav small{color:#60758e;padding:18px 12px 6px;text-transform:uppercase;letter-spacing:.08em}
.main{margin-left:248px;width:calc(100% - 248px);height:100vh;overflow-y:auto;overflow-x:hidden;scrollbar-gutter:stable;scrollbar-width:thin;scrollbar-color:rgba(72,168,255,.45) rgba(255,255,255,.03);padding:24px 30px 48px;overscroll-behavior-y:contain}.main::-webkit-scrollbar{width:10px}.main::-webkit-scrollbar-track{background:rgba(255,255,255,.025)}.main::-webkit-scrollbar-thumb{background:rgba(72,168,255,.45);border-radius:999px;border:2px solid transparent;background-clip:padding-box}.main::-webkit-scrollbar-thumb:hover{background:rgba(72,168,255,.68);background-clip:padding-box}.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px}
.title h1{font-size:27px;margin:0 0 3px;letter-spacing:-.02em}.title p{margin:0;color:var(--muted)}
.actions{display:flex;gap:8px;align-items:center}.btn{padding:9px 13px;border-radius:9px;background:rgba(255,255,255,.045);border:1px solid var(--line);color:var(--ink);font-weight:650;transition:.18s ease;box-shadow:inset 0 1px rgba(255,255,255,.04)}
.btn:hover{transform:translateY(-1px);border-color:rgba(72,168,255,.32);background:rgba(255,255,255,.075)}.btn.primary{background:linear-gradient(145deg,#2394ed,#1267b6);color:#fff;border-color:rgba(109,198,255,.38);box-shadow:0 9px 24px rgba(18,103,182,.24)}.btn.primary:hover{background:linear-gradient(145deg,#3aa8f8,#1775ca)}.btn:disabled{opacity:.55;cursor:not-allowed;transform:none}
.view{display:none}.view.active{display:block}.grid{display:grid;gap:15px}.metrics{grid-template-columns:repeat(5,minmax(0,1fr));margin-bottom:16px}
.card{background:linear-gradient(145deg,rgba(18,33,54,.86),rgba(11,24,41,.9));border:1px solid var(--line);border-radius:15px;box-shadow:var(--shadow),inset 0 1px rgba(255,255,255,.035);padding:18px;backdrop-filter:blur(16px);transform:perspective(1200px) translateZ(0)}
.metric{min-height:108px;position:relative;overflow:hidden}.metric:after{content:"";position:absolute;inset:auto -30px -55px auto;width:130px;height:130px;border-radius:50%;background:rgba(72,168,255,.08);filter:blur(3px)}.metric .label{color:var(--muted);font-size:12px;font-weight:650}.metric .value{font-size:28px;font-weight:850;margin-top:10px;letter-spacing:-.03em}.metric .hint{font-size:11px;color:#7890aa;margin-top:2px}
.two{grid-template-columns:1.5fr 1fr}.three{grid-template-columns:repeat(3,1fr)}
.cardhead{display:flex;align-items:center;justify-content:space-between;margin-bottom:13px}.card h2{font-size:16px;margin:0}.cardhead p{margin:3px 0 0;color:var(--muted);font-size:12px}
.health{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:750;color:#b7c8da}.dot{width:8px;height:8px;border-radius:50%;background:var(--green);display:inline-block;box-shadow:0 0 12px currentColor}.dot.amber{background:var(--amber)}.dot.red{background:var(--red)}
.hero{background:linear-gradient(135deg,rgba(12,43,73,.95),rgba(15,105,183,.86));color:#fff;padding:25px;border-radius:16px;border:1px solid rgba(113,194,255,.22);box-shadow:0 22px 55px rgba(0,79,145,.22),inset 0 1px rgba(255,255,255,.08);margin-bottom:16px;position:relative;overflow:hidden}.hero:after{content:"";position:absolute;width:280px;height:280px;right:-90px;top:-120px;border-radius:50%;background:rgba(255,255,255,.08);filter:blur(2px)}.hero h2{margin:0 0 6px;font-size:23px}.hero p{color:#d7eaff;margin:0 0 16px;max-width:720px}.hero .btn{background:#fff;color:#0a66c2;border-color:#fff;position:relative;z-index:1}
.quick{grid-template-columns:repeat(4,1fr)}.quick button{padding:16px;text-align:left;background:linear-gradient(145deg,rgba(20,38,61,.88),rgba(12,25,43,.9));color:var(--ink);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);transition:.18s ease}.quick button:hover{border-color:rgba(72,168,255,.32);transform:translateY(-2px) rotateX(.4deg)}.quick b{display:block}.quick span{display:block;color:var(--muted);font-size:11px;margin-top:3px}
pre{white-space:pre-wrap;word-break:break-word;max-height:420px;overflow:auto;background:#040a12;color:#cfe3f7;padding:15px;border:1px solid var(--line);border-radius:10px;margin:0;font-size:12px}
.system-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.system-status{display:flex;align-items:center;gap:9px;margin-top:12px;padding:10px;border:1px solid var(--line);border-radius:9px;background:rgba(255,255,255,.025);font-size:10px;color:var(--muted)}.mini-run{display:grid;gap:9px}.mini-run .agent-last-grid{margin-top:0}@media(max-width:800px){.system-grid{grid-template-columns:repeat(2,1fr)}}.approval-hero{display:flex;align-items:center;gap:14px;padding:18px;background:linear-gradient(135deg,rgba(72,168,255,.09),rgba(50,213,131,.05))}.approval-hero-icon{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;background:rgba(50,213,131,.12);color:#7af0b0;font-size:20px;font-weight:900;border:1px solid rgba(50,213,131,.2)}.approval-hero h2{margin:2px 0 4px;font-size:17px}.approval-hero p{margin:0;color:var(--muted);font-size:11px;max-width:760px}.approval-flow{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;align-items:center;gap:10px;margin-top:12px;padding:13px 15px;border:1px solid var(--line);border-radius:12px;background:rgba(255,255,255,.02)}.approval-flow>div:not(.approval-arrow){display:grid;grid-template-columns:25px 1fr;column-gap:8px;align-items:center}.approval-flow span{grid-row:span 2;width:25px;height:25px;border-radius:50%;display:grid;place-items:center;background:rgba(72,168,255,.12);color:#9ed8ff;font-weight:800;font-size:11px}.approval-flow b{font-size:11px}.approval-flow small{color:var(--muted);font-size:9px}.approval-arrow{color:#526b86;font-size:18px}.approval-list{display:grid;gap:10px}.approval-card{padding:15px;border:1px solid var(--line);border-radius:12px;background:linear-gradient(145deg,rgba(20,38,61,.72),rgba(10,23,39,.82))}.approval-card-head{display:flex;justify-content:space-between;gap:10px}.approval-card h3{margin:7px 0 2px;text-transform:capitalize;font-size:14px}.approval-target{font-size:12px;color:#9ed8ff;font-weight:700}.approval-date{font-size:10px;color:var(--muted)}.approval-proposal{margin-top:12px;padding:11px;border-radius:9px;background:rgba(255,255,255,.035);border:1px solid rgba(154,181,211,.10);font-size:11px;line-height:1.55;white-space:pre-wrap;overflow-wrap:anywhere}.approval-label{font-size:9px;text-transform:uppercase;letter-spacing:.06em;color:#7189a2;margin-bottom:4px}.approval-safety{margin-top:9px;padding:9px;border-radius:8px;background:rgba(253,176,34,.06);color:#d8c18b;font-size:10px}.approval-actions{display:flex;gap:8px;margin-top:12px}.approval-empty{text-align:center;padding:28px 15px}.approval-empty-icon{margin:auto;width:40px;height:40px;border-radius:50%;display:grid;place-items:center;background:rgba(50,213,131,.10);color:#7af0b0;font-weight:900}.approval-empty h3{margin:8px 0 2px}.approval-empty p{margin:0;color:#b7c8da;font-size:12px}.approval-empty small{display:block;margin-top:5px;color:var(--muted);font-size:10px}@media(max-width:700px){.approval-flow{grid-template-columns:1fr}.approval-arrow{display:none}.approval-card-head{flex-direction:column}.approval-date{margin-top:-5px}}.agent-result{display:grid;gap:14px}.agent-success{display:flex;justify-content:space-between;align-items:center;gap:15px;padding:15px;border-radius:12px;background:linear-gradient(135deg,rgba(50,213,131,.10),rgba(72,168,255,.05));border:1px solid rgba(50,213,131,.18)}.agent-success h3{margin:7px 0 2px;font-size:15px}.agent-success p{margin:0;color:var(--muted);font-size:11px}.agent-safe{font-size:10px;color:#9be7bb;white-space:nowrap}.agent-summary-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}.agent-metric{padding:11px;border:1px solid var(--line);border-radius:10px;background:rgba(255,255,255,.025)}.agent-metric span{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:#7189a2}.agent-metric b{display:block;font-size:18px;margin-top:4px}.agent-metric small{display:block;color:#7189a2;font-size:9px;margin-top:2px}.agent-section{padding:14px;border:1px solid var(--line);border-radius:12px;background:rgba(255,255,255,.018)}.agent-section-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}.agent-section-head h3{margin:0;font-size:14px}.agent-section-head p{margin:2px 0 0;color:var(--muted);font-size:11px}.agent-job-list,.agent-post-list{display:grid;gap:7px}.agent-job{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:11px;border-radius:9px;background:rgba(255,255,255,.035);border:1px solid rgba(154,181,211,.10)}.agent-job-title{font-size:12px;font-weight:800}.agent-job-title a{color:#9ed8ff;text-decoration:none}.agent-job-title a:hover{text-decoration:underline}.agent-job-meta{font-size:10px;color:var(--muted);margin-top:3px}.agent-job-actions{display:flex;align-items:center;gap:6px}.agent-post{padding:11px;border-radius:9px;background:rgba(255,255,255,.035);border:1px solid rgba(154,181,211,.10)}.agent-post-author{font-weight:800;font-size:12px}.agent-post-text{font-size:11px;color:#cbd8e7;margin:5px 0 7px;line-height:1.5}.agent-empty{padding:15px;text-align:center;color:var(--muted);font-size:11px}.agent-tech{border:1px solid var(--line);border-radius:10px;background:rgba(255,255,255,.018);padding:10px}.agent-tech summary{cursor:pointer;color:#9db1c8;font-size:11px;font-weight:750}.agent-tech summary span{float:right;color:#60758e}.agent-tech pre{margin-top:10px;max-height:300px}.agent-health-card{padding:13px;border:1px solid var(--line);border-radius:12px;background:rgba(255,255,255,.025)}.agent-health-row{display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:10px;color:var(--muted)}.agent-last-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:7px;margin-top:10px}.agent-note{margin-top:10px;padding:9px;border-radius:8px;background:rgba(50,213,131,.06);color:#8ce9b5;font-size:10px}@media(max-width:1100px){.agent-summary-grid{grid-template-columns:repeat(3,1fr)}}@media(max-width:650px){.agent-success,.agent-job{flex-direction:column;align-items:flex-start}.agent-summary-grid{grid-template-columns:repeat(2,1fr)}.agent-job-actions{width:100%}.agent-safe{white-space:normal}}.run-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px}.run-chip{padding:10px;border-radius:10px;background:rgba(255,255,255,.035);border:1px solid var(--line)}.run-chip b{display:block;font-size:16px}.run-chip span{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}.section-kicker{font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:#6f87a0;font-weight:800;margin-bottom:5px}.nav-section{font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:#526a83;padding:16px 12px 5px;font-weight:800}.live-pill{display:inline-flex;align-items:center;gap:6px;padding:5px 9px;border-radius:999px;background:rgba(50,213,131,.08);border:1px solid rgba(50,213,131,.16);color:#7be9ae;font-size:10px;font-weight:800}.live-pill i{width:6px;height:6px;border-radius:50%;background:currentColor}.drawerbox{width:min(760px,96vw)}.table td{font-size:12px}.table th{white-space:nowrap}.app-detail-grid{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:9px;padding:12px;background:rgba(255,255,255,.025);border:1px solid var(--line);border-radius:10px}.app-detail-grid label{display:grid;gap:4px;color:var(--muted);font-size:10px;font-weight:700}.app-detail-grid input,.app-detail-grid textarea{width:100%;padding:8px;border-radius:7px;border:1px solid var(--line);background:rgba(0,0,0,.18);color:var(--ink)}.app-detail-grid textarea{min-height:58px;resize:vertical}.app-detail-grid .wide{grid-column:span 3}@media(max-width:1000px){.app-detail-grid{grid-template-columns:repeat(2,minmax(150px,1fr))}.app-detail-grid .wide{grid-column:span 2}}@media(max-width:650px){.result-head{flex-direction:column}.drawerbox{width:100%}}
.application-overview{margin-bottom:16px}.application-metrics{grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.application-metrics button{min-height:82px;padding:14px 16px}.application-metrics b{font-size:20px}.application-shell{padding:20px}.application-header{display:flex;justify-content:space-between;align-items:flex-end;gap:18px;margin-bottom:16px}.application-header h2{margin:0;font-size:21px;letter-spacing:-.02em}.application-header p{margin:4px 0 0;color:var(--muted);font-size:12px}.application-toolbar{display:flex;align-items:center;gap:8px}.application-toolbar .search{width:280px}.pipeline-strip{display:flex;gap:8px;overflow:auto;padding:3px 0 15px;border-bottom:1px solid var(--line);scrollbar-width:thin}.pipeline-stage{display:flex;align-items:center;gap:7px;white-space:nowrap;padding:7px 11px;border:1px solid var(--line);border-radius:999px;background:rgba(255,255,255,.025);color:#9fb3c8;font-size:10px;font-weight:750}.pipeline-stage .count{min-width:20px;height:20px;display:grid;place-items:center;border-radius:999px;background:rgba(72,168,255,.12);color:#a7d9ff}.application-table-wrap{margin-top:4px}.application-table{min-width:960px;table-layout:fixed}.application-table th{padding:13px 10px;background:rgba(8,19,33,.92);position:sticky;top:0;z-index:1}.application-table td{padding:13px 10px}.application-table tbody tr:not(.app-details):hover{background:rgba(72,168,255,.045)}.application-table th:nth-child(1),.application-table td:nth-child(1){width:24%}.application-table th:nth-child(2),.application-table td:nth-child(2){width:15%}.application-table th:nth-child(3),.application-table td:nth-child(3){width:9%}.application-table th:nth-child(4),.application-table td:nth-child(4){width:10%}.application-table th:nth-child(5),.application-table td:nth-child(5){width:9%}.application-table th:nth-child(6),.application-table td:nth-child(6){width:10%}.application-table th:nth-child(7),.application-table td:nth-child(7){width:9%}.application-table th:nth-child(8),.application-table td:nth-child(8){width:14%}.application-table tbody tr:not(.app-details) td{overflow:hidden}.application-table .statusSelect{width:100%;min-width:0;padding:7px 7px;border-radius:7px;border:1px solid var(--line);background:rgba(255,255,255,.045);color:var(--ink)}.application-table .app-details td{padding:8px 10px 14px}.application-table .muted{font-size:10px;margin-top:3px;color:#728aa3}.application-table .application-actions{display:flex;flex-wrap:wrap;gap:6px;align-items:center;min-width:0}.application-table .btn{padding:7px 8px;font-size:10px;white-space:nowrap}.application-table .application-actions .btn{flex:0 0 auto}.app-detail-grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:12px;padding:18px;margin-top:4px;background:linear-gradient(145deg,rgba(9,20,35,.96),rgba(14,30,50,.92));border:1px solid rgba(118,157,196,.18);border-radius:14px;box-shadow:inset 0 1px rgba(255,255,255,.035)}.app-detail-grid label{display:grid;gap:6px;color:#8ea5bd;font-size:10px;font-weight:750;text-transform:uppercase;letter-spacing:.05em;min-width:0}.app-detail-grid label:nth-child(-n+8){grid-column:span 3}.app-detail-grid .wide{grid-column:span 9!important}.app-detail-grid>div:last-child{grid-column:span 3;display:flex;align-items:end}.app-detail-grid input,.app-detail-grid textarea{width:100%;padding:10px 11px;border-radius:9px;border:1px solid rgba(130,165,201,.18);background:rgba(3,10,19,.58);color:var(--ink);outline:none;transition:.16s ease}.app-detail-grid input:focus,.app-detail-grid textarea:focus{border-color:rgba(72,168,255,.65);box-shadow:0 0 0 3px rgba(72,168,255,.10)}.app-detail-grid textarea{min-height:76px;resize:vertical}.app-detail-grid .btn{width:100%;min-height:40px}.application-table .app-details{display:none}.application-table .app-details.open{display:table-row}@media(max-width:1100px){.application-header{align-items:flex-start;flex-direction:column}.application-toolbar{width:100%}.application-toolbar .search{flex:1;width:auto}.application-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}.app-detail-grid label:nth-child(-n+8){grid-column:span 6}.app-detail-grid .wide{grid-column:span 8!important}.app-detail-grid>div:last-child{grid-column:span 4}}@media(max-width:700px){.application-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.application-toolbar{flex-direction:column;align-items:stretch}.application-toolbar .search{width:100%}.app-detail-grid{grid-template-columns:1fr}.app-detail-grid label:nth-child(-n+8),.app-detail-grid .wide,.app-detail-grid>div:last-child{grid-column:1!important}.application-shell{padding:14px}}.tablewrap{overflow:auto}.table{width:100%;border-collapse:collapse}.table th{font-size:11px;text-transform:uppercase;color:#7890aa;letter-spacing:.04em;text-align:left;padding:10px 8px;border-bottom:1px solid var(--line)}.table td{padding:11px 8px;border-bottom:1px solid rgba(154,181,211,.09);vertical-align:top}.table tr:hover td{background:rgba(72,168,255,.035)}
.badge{display:inline-flex;padding:3px 8px;border-radius:999px;background:rgba(72,168,255,.12);color:#8dccff;font-size:11px;font-weight:700;border:1px solid rgba(72,168,255,.12)}.badge.green{background:rgba(50,213,131,.1);color:#70e7aa}.badge.amber{background:rgba(253,176,34,.1);color:#ffd27a}.badge.red{background:rgba(249,112,102,.1);color:#ffaaa3}
.muted{color:var(--muted)}.error{padding:12px;background:rgba(249,112,102,.08);border:1px solid rgba(249,112,102,.24);color:#ffaaa3;border-radius:9px}.empty{padding:30px;text-align:center;color:var(--muted)}
.skills{grid-template-columns:repeat(3,1fr)}.skill{border:1px solid var(--line);border-radius:12px;padding:15px;background:linear-gradient(145deg,rgba(20,38,61,.72),rgba(11,25,42,.78));box-shadow:0 10px 30px rgba(0,0,0,.14);transition:.18s ease}.skill:hover{border-color:rgba(72,168,255,.32);box-shadow:0 16px 38px rgba(0,0,0,.22);transform:translateY(-2px)}.skilltop{display:flex;justify-content:space-between;gap:10px}.skill h3{font-size:14px;margin:0 0 5px;text-transform:capitalize}.skill p{font-size:12px;color:var(--muted);margin:0 0 12px}.skill .btn{padding:7px 10px}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}.search{flex:1;min-width:220px;padding:10px 12px;border:1px solid var(--line);border-radius:9px;background:rgba(255,255,255,.045);color:var(--ink);outline:none}.search:focus,.field input:focus,.field textarea:focus,.field select:focus{border-color:rgba(72,168,255,.55);box-shadow:0 0 0 3px rgba(72,168,255,.08)}
.drawer{position:fixed;inset:0;background:rgba(1,7,14,.72);z-index:20;display:none;backdrop-filter:blur(8px)}.drawer.open{display:block}.drawerbox{position:absolute;right:0;top:0;height:100%;width:min(620px,95vw);background:linear-gradient(160deg,#102238,#081522);border-left:1px solid var(--line);padding:24px;overflow:auto;box-shadow:-20px 0 70px rgba(0,0,0,.38)}.drawerhead{display:flex;justify-content:space-between;align-items:flex-start}.drawer h2{margin:0}.field{margin:15px 0}.field label{display:block;font-size:12px;font-weight:700;margin-bottom:6px;color:#c7d6e7}.field input,.field textarea,.field select{width:100%;border:1px solid var(--line);border-radius:8px;padding:10px;background:rgba(255,255,255,.045);color:var(--ink);outline:none}.field textarea{min-height:120px;resize:vertical}.readonly{background:#f8fafc}.notice{padding:11px;border-radius:8px;background:rgba(72,168,255,.08);border:1px solid rgba(72,168,255,.15);color:#a9d8ff;font-size:12px}.danger{color:#ffaaa3}
.task{padding:12px;border:1px solid var(--line);border-radius:9px;background:rgba(255,255,255,.035);margin-top:10px}.progress{height:7px;background:rgba(255,255,255,.08);border-radius:99px;overflow:hidden;margin-top:8px}.progress i{display:block;height:100%;width:35%;background:linear-gradient(90deg,#48a8ff,#8dd4ff);animation:load 1.2s infinite ease-in-out alternate}@keyframes load{to{width:85%}}
@media(max-width:1000px){.sidebar{width:70px}.brand span,.brand strong,.nav small,.nav button span{display:none}.nav button{text-align:center}.main{margin-left:70px;width:calc(100% - 70px)}.metrics{grid-template-columns:repeat(2,1fr)}.quick,.skills,.two,.three{grid-template-columns:1fr 1fr}}
@media(max-width:650px){.sidebar{display:none}.main{margin:0;width:100%;padding:15px}.metrics,.quick,.skills,.two,.three{grid-template-columns:1fr}.topbar{align-items:flex-start;gap:10px}.actions{flex-wrap:wrap}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important;animation:none!important}.quick button:hover,.skill:hover,.nav button:hover{transform:none}}
</style>
</head>
<body>
<div class="app">
<aside class="sidebar">
  <div class="brand"><div class="brand-mark">in</div><div><strong>LinkedIn Agent</strong><span>Control Center</span></div></div>
  <nav class="nav">
    <div class="nav-section">Workspace</div>
    <button class="active" data-view="overview">⌂ <span>Overview</span></button>
    <button data-view="skills">✦ <span>Skill Center</span></button>
    <button data-view="jobs">▣ <span>Jobs</span></button>
    <button data-view="applications">✓ <span>Applications</span></button>
    <div class="nav-section">Governance</div>
    <button data-view="approvals">⚑ <span>Approvals</span></button>
    <button data-view="agent">◉ <span>Agent Runs</span></button>
    <div class="nav-section">Operations</div>
    <button data-view="system">⚙ <span>System</span></button>
  </nav>
  <div style="position:absolute;left:14px;right:14px;bottom:18px;color:#667085;font-size:11px">Local-only<br>Human approval protected</div>
</aside>
<main class="main">
<header class="topbar">
  <div class="title"><h1 id="pageTitle">Overview</h1><p>Read, research, draft and approve — from one place.</p></div>
  <div class="actions"><span id="health" class="health"><i class="dot"></i> Checking</span><span class="live-pill"><i></i> READ-ONLY · 30M CADENCE · 6H FRESHNESS</span><button class="btn" onclick="refreshAll()">↻ Refresh</button><button class="btn primary" onclick="startAgent()">Run Agent</button></div>
</header>

<section id="overview" class="view active">
  <div class="grid metrics" id="metrics"></div>
  <div class="hero"><div class="section-kicker" style="color:#9bd6ff">COMMAND CENTER</div><h2>Discover opportunities. Review signals. Stay in control.</h2><p>The agent continuously discovers jobs and hiring signals while keeping account-changing actions behind human approval. Use the workspace below to review results, manage your pipeline and launch individual skills.</p><div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" onclick="showView('jobs')">Review jobs →</button><button class="btn" onclick="openSkill('profile_optimizer')">Optimize LinkedIn profile →</button><button class="btn" onclick="showView('skills')">Open Skill Center →</button></div></div>
  <div class="grid quick">
    <button onclick="openSkill('jobs')"><b>Find Power BI jobs</b><span>LinkedIn · Delhi / Gurgaon / Noida / Remote India</span></button>
    <button onclick="openSkill('people')"><b>Find recruiters</b><span>People research · read-only</span></button>
    <button onclick="openSkill('posts')"><b>Find hiring posts</b><span>Content search · read-only</span></button>
    <button onclick="openSkill('post_writer')"><b>Write a LinkedIn post</b><span>Local drafting · approval before publish</span></button>
  </div>
  <div class="grid two" style="margin-top:16px">
    <div class="card"><div class="cardhead"><div><h2>Recent jobs</h2><p>Latest records stored locally</p></div><button class="btn" onclick="showView('jobs')">View all</button></div><div class="tablewrap"><table class="table" id="overviewJobs"></table></div></div>
    <div class="card"><div class="cardhead"><div><h2>Last agent run</h2><p id="runMeta">Loading…</p></div></div><div id="lastRun"></div></div>
  </div>
</section>

<section id="skills" class="view">
  <div class="card">
    <div class="cardhead"><div><h2>Skill Center</h2><p>All registered skills, using the repository's real skill adapters.</p></div></div>
    <div class="toolbar"><input class="search" id="skillSearch" placeholder="Search skills, e.g. recruiter, post, humanizer…"><select id="modeFilter"><option value="">All modes</option><option value="read">Read</option><option value="local">Draft / Analyze</option><option value="approval">Approval</option></select></div>
    <div class="grid skills" id="skillGrid"></div>
  </div>
</section>

<section id="jobs" class="view"><div class="card"><div class="cardhead"><div><h2>Job Intelligence</h2><p>Stored discovery history and application signals.</p></div><button class="btn primary" onclick="openSkill('jobs')">Search LinkedIn jobs</button></div><div class="toolbar"><input class="search" id="jobSearch" placeholder="Search role, company, location…"><select id="jobStatusFilter"><option value="">All statuses</option><option value="new">New</option><option value="shortlisted">Shortlisted</option><option value="drafted">Drafted</option><option value="applied">Applied</option><option value="screening">Screening</option><option value="interview">Interview</option><option value="offer">Offer</option><option value="rejected">Rejected</option><option value="withdrawn">Withdrawn</option><option value="closed">Closed</option></select><select id="jobWorkplaceFilter"><option value="">All workplace types</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="on-site">On-site</option></select><select id="jobScoreSort" title="Sort jobs by score"><option value="desc">Score: High → Low</option><option value="asc">Score: Low → High</option></select></div><div class="tablewrap"><table class="table" id="jobsTable"></table></div></div></section>
<section id="applications" class="view">
<div class="application-overview">
  <div class="grid quick application-metrics" id="applicationMetrics"></div>
</div>
<div class="card application-shell">
  <div class="application-header">
    <div><div class="section-kicker">Career pipeline</div><h2>Application Workspace</h2><p>Keep every opportunity, follow-up, interview and offer organized in one place.</p></div>
    <div class="application-toolbar"><input class="search" id="appSearch" placeholder="Search role, company or recruiter…"><select id="appStatusFilter" class="btn"><option value="">All stages</option><option value="new">New</option><option value="shortlisted">Shortlisted</option><option value="drafted">Drafted</option><option value="applied">Applied</option><option value="screening">Screening</option><option value="interview">Interview</option><option value="offer">Offer</option><option value="rejected">Rejected</option><option value="withdrawn">Withdrawn</option><option value="closed">Closed</option></select></div>
  </div>
  <div class="pipeline-strip" id="applicationPipelineStrip"></div>
  <div class="tablewrap application-table-wrap"><table class="table application-table" id="appsTable"></table></div>
</div>
</section>
<section id="approvals" class="view">
<div class="card approval-hero"><div class="approval-hero-icon">✓</div><div><div class="section-kicker">GOVERNANCE GATE</div><h2>Review before LinkedIn actions</h2><p>Anything that could contact, publish, engage, or change your LinkedIn account must stay under your control. Review an item, then approve or reject it.</p></div></div>
<div class="approval-flow"><div><span>1</span><b>Prepare</b><small>Automation creates a review item</small></div><div class="approval-arrow">→</div><div><span>2</span><b>Review</b><small>You inspect the target and proposed action</small></div><div class="approval-arrow">→</div><div><span>3</span><b>Decide</b><small>Approve or reject explicitly</small></div></div>
<div class="card" style="margin-top:14px"><div class="cardhead"><div><h2>Pending approvals</h2><p id="approvalSummary">No pending actions.</p></div><span id="approvalCount" class="badge amber">0 pending</span></div><div id="approvalCards"></div></div>
</section>
<section id="agent" class="view">
<div class="grid two">
 <div class="card"><div class="cardhead"><div><h2>Agent Runs</h2><p>Run the complete governed discovery cycle.</p></div><button class="btn primary" onclick="startAgent()">Run Agent Now</button></div><div id="tasks"></div></div>
 <div class="card"><div class="cardhead"><div><h2>Last run</h2><p>Simple health summary. Technical diagnostics stay hidden.</p></div></div><div id="agentDetails"></div></div>
</div>
<div class="card" style="margin-top:15px"><div class="cardhead"><div><h2>Recent activity</h2><p>Local audit trail from the application database.</p></div></div><div class="tablewrap"><table class="table" id="activityTable"></table></div></div>
</section>
<section id="system" class="view"><div class="grid three"><div class="card"><h2>Safety</h2><p class="muted">Read-only LinkedIn discovery is automatic. Account-changing workflows remain approval-gated.</p></div><div class="card"><h2>Browser</h2><p class="muted">Uses your persistent local Playwright profile. Credentials remain on your machine.</p></div><div class="card"><h2>Performance</h2><p class="muted">Dashboard requests return immediately for long-running skills and poll for completion.</p></div></div><div class="card" style="margin-top:14px"><div class="cardhead"><div><h2>System health</h2><p>Local service status and operational checks.</p></div></div><div id="systemDetails"></div></div></section>
</main>
</div>

<div class="drawer" id="drawer" onclick="if(event.target===this)closeDrawer()">
 <div class="drawerbox">
  <div class="drawerhead"><div><h2 id="drawerTitle">Run skill</h2><p id="drawerDesc" class="muted"></p></div><button class="btn" onclick="closeDrawer()">✕</button></div>
  <div id="drawerSafety" class="notice" style="margin-top:14px"></div>
  <form id="skillForm" onsubmit="submitSkill(event)"><div id="skillFields"></div><button class="btn primary" type="submit" id="skillSubmit">Run skill</button></form>
  <div id="skillTask"></div><div id="skillOutput" style="margin-top:16px"></div>
 </div>
</div>

<script>
let state={summary:null,skills:[],activeSkill:null,taskIds:[]};
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function api(path,opts={}){
 const ctrl=new AbortController(); const t=setTimeout(()=>ctrl.abort(),7000);
 try{const r=await fetch(path,{...opts,signal:ctrl.signal}); const tx=await r.text(); let d={}; try{d=tx?JSON.parse(tx):{}}catch(_){d={error:tx}};
 clearTimeout(t); if(!r.ok)throw Error(d.error||r.statusText); return d;
 }catch(e){clearTimeout(t); if(e.name==='AbortError')throw Error('Dashboard API timed out'); throw e}
}
function showView(id){
 document.querySelectorAll('.view').forEach(x=>x.classList.remove('active'));
 document.getElementById(id).classList.add('active');
 document.querySelectorAll('.nav button').forEach(x=>x.classList.toggle('active',x.dataset.view===id));
 const names={overview:'Overview',skills:'Skill Center',jobs:'Job Intelligence',applications:'Applications',approvals:'Approval Queue',agent:'Agent Runs',system:'System'};
 document.getElementById('pageTitle').textContent=names[id]||id;
 window.scrollTo({top:0,behavior:'smooth'});
}
document.querySelectorAll('.nav button').forEach(b=>b.onclick=()=>showView(b.dataset.view));

function renderMetrics(d){
 const items=[['Jobs tracked',d.jobs_tracked,'Local history'],['Applications',d.application_count,'Pipeline'],['Pending approvals',d.pending_approvals,'Human review'],['Recent jobs',d.recent_jobs,'Latest 50'],['Agent health',(d.last_run?.health_state||d.last_run?.last_status||'—'),'Latest cycle']];
 document.getElementById('metrics').innerHTML=items.map(x=>'<div class="card metric"><div class="label">'+esc(x[0])+'</div><div class="value">'+esc(x[1])+'</div><div class="hint">'+esc(x[2])+'</div></div>').join('');
 const healthy=(d.last_run?.health_state||'').toUpperCase()==='HEALTHY';
 document.getElementById('health').innerHTML='<i class="dot '+(healthy?'':'amber')+'"></i> '+esc(d.last_run?.health_state||'UNKNOWN');
}
function jobRows(rows){
 const list=rows||[];
 const tracked=new Set((state.summary?.applications||[]).map(x=>String(x?.job_url||'').trim()).filter(Boolean));
 return '<thead><tr><th>Role</th><th>Company</th><th>Location</th><th>Workplace</th><th>Score ↕</th><th>Status</th><th>Seen</th><th>Application</th></tr></thead><tbody>'+
 (list.length ? list.map(x=>{
   const link=x.url?'<a href="'+esc(x.url)+'" target="_blank" rel="noopener noreferrer" style="color:#8dccff;text-decoration:none">'+esc(x.title)+'</a>':'<b>'+esc(x.title)+'</b>';
   const wp=x.workplace_type||((String(x.location||'').toLowerCase().includes('remote'))?'remote':'');
   const reason=String(x.reasons||'').slice(0,180);
   const score=Number.isFinite(Number(x.score))?Number(x.score):'—';
   const isTracked=tracked.has(String(x.url||'').trim());
   const applicationButton=isTracked
     ? '<button class="btn" disabled>Tracked</button>'
     : '<button class="btn" onclick="addApplication(this)" data-url="'+esc(x.url||'')+'" data-title="'+esc(x.title||'')+'" data-company="'+esc(x.company||'')+'" data-location="'+esc(x.location||'')+'">Track application</button>';
   return '<tr><td><b>'+link+'</b>'+(reason?'<div class="muted" style="font-size:11px;margin-top:3px">'+esc(reason)+'</div>':'')+'</td><td>'+esc(x.company)+'</td><td>'+esc(x.location)+'</td><td>'+(wp?'<span class="badge green">'+esc(wp)+'</span>':'<span class="muted">—</span>')+'</td><td><span class="score '+scoreClass(score)+'">'+esc(score)+'</span></td><td><span class="badge">'+esc(x.status||'new')+'</span></td><td>'+esc(x.updated_at)+'</td><td>'+applicationButton+'</td></tr>';
 }).join('') : '<tr><td colspan="8" class="empty">No jobs stored yet.</td></tr>')+
 '</tbody>';
}
function normalizeFilterValue(value){
 return String(value??'').trim().toLowerCase().replace(/_/g,'-');
}
async function addApplication(button){
 const data={job_url:button.dataset.url,title:button.dataset.title,company:button.dataset.company,location:button.dataset.location,source:'LinkedIn'};
 if(!data.job_url){alert('This job has no application URL.');return}
 button.disabled=true;
 try{const d=await api('/api/applications/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});button.textContent=d.added?'Tracked':'Already tracked';refreshAll()}
 catch(e){alert(e.message);button.disabled=false}
}
function filterJobs(){
 const q=(document.getElementById('jobSearch')?.value||'').toLowerCase().trim();
 const status=normalizeFilterValue(document.getElementById('jobStatusFilter')?.value||'');
 const workplace=normalizeFilterValue(document.getElementById('jobWorkplaceFilter')?.value||'');
 const direction=document.getElementById('jobScoreSort')?.value||'desc';
 const allJobs=Array.isArray(state.summary?.jobs)?state.summary.jobs:[];
 const rows=allJobs.filter(x=>{
   const hay=[x.title,x.company,x.location,x.reasons].join(' ').toLowerCase();
   const wp=normalizeFilterValue(x.workplace_type||((String(x.location||'').toLowerCase().includes('remote'))?'remote':''));
   const jobStatus=normalizeFilterValue(x.status||'new');
   return (!q||hay.includes(q))&&(!status||status==='all'||jobStatus===status)&&(!workplace||workplace==='all'||wp===workplace);
 }).sort((a,b)=>{
   const av=Number(a.score), bv=Number(b.score);
   const an=Number.isFinite(av)?av:-Infinity, bn=Number.isFinite(bv)?bv:-Infinity;
   return direction==='asc' ? an-bn : bn-an;
 });
 document.getElementById('jobsTable').innerHTML=jobRows(rows);
}
function displayApplicationValue(value){
 const text=String(value??'').trim();
 return text ? esc(text) : '<span class="muted">Not set</span>';
}
function renderTables(d){
 document.getElementById('jobsTable').innerHTML=jobRows(d.jobs);
 filterJobs();
 document.getElementById('overviewJobs').innerHTML=jobRows((d.jobs||[]).slice(0,8));
 const apps=d.applications||[];
 const counts={new:0,shortlisted:0,applied:0,screening:0,interview:0,offer:0};
 apps.forEach(x=>{if(Object.prototype.hasOwnProperty.call(counts,x.status))counts[x.status]++});
 document.getElementById('applicationMetrics').innerHTML=
   [['Total',apps.length,'Tracked opportunities'],['Applied',counts.applied,'Submitted'],['Screening',counts.screening,'In progress'],['Interview',counts.interview,'Scheduled'],['Offer',counts.offer,'Offers']].map(x=>'<button type="button"><b>'+esc(String(x[1]))+'</b><span>'+esc(x[0])+'</span><small>'+esc(x[2])+'</small></button>').join('');
 const stages=['new','shortlisted','drafted','applied','screening','interview','offer','rejected','withdrawn','closed'];
 document.getElementById('applicationPipelineStrip').innerHTML=stages.map(s=>{
   const n=apps.filter(x=>x.status===s).length;
   return '<button class="pipeline-stage" type="button" onclick="document.getElementById(\'appStatusFilter\').value=\''+s+'\';filterApplications()"><span>'+esc(s.replaceAll('_',' '))+'</span><span class="count">'+n+'</span></button>';
 }).join('');
 const renderAppRow=x=>{
   const editId='app-'+Math.random().toString(36).slice(2);
   const options=[x.status,...(x.allowed_transitions||[])].filter((v,i,a)=>a.indexOf(v)===i).map(s=>'<option value="'+esc(s)+'" '+(s===x.status?'selected':'')+'>'+esc(s)+'</option>').join('');
   return '<tr><td><b>'+esc(x.title)+'</b><div class="muted">'+esc(x.location||'')+'</div></td><td>'+esc(x.company)+'</td><td>'+esc(x.source||'—')+'</td><td><select class="statusSelect" data-url="'+esc(x.job_url)+'" data-current="'+esc(x.status)+'">'+options+'</select></td><td>'+displayApplicationValue(x.applied_at)+'</td><td>'+displayApplicationValue(x.next_follow_up)+'</td><td>'+displayApplicationValue(x.recruiter)+'</td><td><div class="application-actions"><a class="btn" href="'+esc(x.job_url)+'" target="_blank" rel="noopener noreferrer">Open ↗</a><button class="btn" onclick="transitionApplication(this)">Save stage</button><button class="btn" onclick="toggleAppDetails(this)">Edit details</button></div></td></tr>'+
   '<tr class="app-details"><td colspan="8"><div class="app-detail-grid">'+
   '<label>Source<input data-field="source" value="'+esc(x.source||'')+'" placeholder="LinkedIn / Naukri / Company"></label>'+
   '<label>Location<input data-field="location" value="'+esc(x.location||'')+'" placeholder="Gurgaon / Remote India"></label>'+
   '<label>Recruiter<input data-field="recruiter" value="'+esc(x.recruiter||'')+'" placeholder="Name / email"></label>'+
   '<label>Resume version<input data-field="resume_version" value="'+esc(x.resume_version||'')+'" placeholder="Resume v3"></label>'+
   '<label>Applied date<input data-field="applied_at" type="date" value="'+esc((x.applied_at||'').slice(0,10))+'"></label>'+
   '<label>Follow-up date<input data-field="next_follow_up" type="date" value="'+esc((x.next_follow_up||'').slice(0,10))+'"></label>'+
   '<label>Interview date<input data-field="interview_date" type="date" value="'+esc((x.interview_date||'').slice(0,10))+'"></label>'+
   '<label>Salary / CTC notes<input data-field="salary_notes" value="'+esc(x.salary_notes||'')+'" placeholder="e.g. 18 LPA"></label>'+
   '<label class="wide">Notes<textarea data-field="notes" placeholder="Follow-up notes, recruiter response, interview feedback…">'+esc(x.notes||'')+'</textarea></label>'+
   '<div><button class="btn primary" onclick="saveApplicationDetails(this)" data-url="'+esc(x.job_url)+'">Save details</button></div></div></td></tr>';
 };
 document.getElementById('appsTable').innerHTML='<thead><tr><th>Role</th><th>Company</th><th>Source</th><th>Status</th><th>Applied</th><th>Next follow-up</th><th>Recruiter</th><th>Actions</th></tr></thead><tbody>'+apps.map(renderAppRow).join('')+'</tbody>';
 filterApplications();
 document.getElementById('activityTable').innerHTML='<thead><tr><th>Time</th><th>Action</th><th>Target</th><th>Status</th><th>Details</th></tr></thead><tbody>'+
 (d.activity||[]).map(x=>'<tr><td>'+esc(x.created_at)+'</td><td>'+esc(x.action)+'</td><td>'+esc(x.target)+'</td><td><span class="badge">'+esc(x.status)+'</span></td><td>'+esc(x.details)+'</td></tr>').join('')+'</tbody>';
 const approvals=d.approvals||[];
 document.getElementById('approvalCount').textContent=approvals.length+' pending';
 document.getElementById('approvalSummary').textContent=approvals.length?approvals.length+' action'+(approvals.length===1?'':'s')+' waiting for your review.':'Nothing is waiting for approval.';
 document.getElementById('approvalCards').innerHTML=approvals.length?'<div class="approval-list">'+approvals.map(x=>{
   const action=String(x.action||'').replace(/^skill:/,'').replaceAll('_',' ');
   const payload=x.payload||'No proposed action details were provided.';
   const target=x.target||'Manual review';
   return '<article class="approval-card"><div class="approval-card-head"><div><span class="badge amber">PENDING REVIEW</span><h3>'+esc(action)+'</h3><div class="approval-target">'+esc(target)+'</div></div><div class="approval-date">'+esc(x.created_at||'')+'</div></div><div class="approval-proposal"><div class="approval-label">Proposed action</div><div>'+esc(payload)+'</div></div><div class="approval-safety">🔒 <b>Your approval is required.</b> This queue records the decision; it does not silently send or publish anything.</div><div class="approval-actions"><button class="btn primary" onclick="decide(\''+esc(x.id)+'\',true)">✓ Approve</button><button class="btn" onclick="decide(\''+esc(x.id)+'\',false)">✕ Reject</button></div></article>';
 }).join('')+'</div>':'<div class="approval-empty"><div class="approval-empty-icon">✓</div><h3>All clear</h3><p>There are no actions waiting for your approval.</p><small>Read-only discovery can continue automatically. Account-changing workflows remain gated here.</small></div>';
}
function renderRun(d){
 const r=d.last_run||{};
 const status=r.health_state||r.last_status||'No run recorded';
 const ok=String(status).toUpperCase()==='HEALTHY'||String(status).toLowerCase()==='success';
 const html='<div class="agent-health-card"><div class="agent-health-row"><span class="badge '+(ok?'green':'amber')+'">'+esc(String(status))+'</span><b>'+(r.last_finished_at?esc(r.last_finished_at):'No run recorded')+'</b></div><div class="agent-last-grid">'+agentMetric('Jobs',r.last_job_count??0,'Last cycle')+agentMetric('New jobs',r.last_new_jobs??0,'Last cycle')+agentMetric('Hiring posts',r.last_hiring_post_count??0,'Last cycle')+agentMetric('Recruiter targets',r.last_recruiter_count??0,'Approval planning')+agentMetric('Duration',formatDuration(r.last_duration_seconds),'Last cycle')+'</div>'+(r.last_error?'<div class="error" style="margin-top:10px">'+esc(r.last_error)+'</div>':'<div class="agent-note">✓ Last cycle completed without an error.</div>')+'</div>';
 document.getElementById('agentDetails').innerHTML=html;
 document.getElementById('lastRun').innerHTML='<div class="mini-run">'+
   '<div class="system-status"><span class="badge '+(ok?'green':'amber')+'">'+esc(String(status))+'</span><span>'+esc(r.last_finished_at||r.updated_at||'No run recorded')+'</span></div>'+
   '<div class="agent-last-grid">'+agentMetric('Jobs',r.last_job_count??0,'Last cycle')+agentMetric('New jobs',r.last_new_jobs??0,'Last cycle')+agentMetric('Hiring posts',r.last_hiring_post_count??0,'Last cycle')+'</div>'+
   '</div>';
 document.getElementById('runMeta').textContent=r.last_finished_at||r.updated_at||'No run recorded';
}
async function refreshAll(){
 try{const [d,s]=await Promise.all([api('/api/summary'),api('/api/skills')]); state.summary=d;state.skills=s.skills||[];renderMetrics(d);renderTables(d);renderRun(d);renderSkills();renderSystem(); if(d.warnings?.length) console.warn(d.warnings)}
 catch(e){document.getElementById('health').innerHTML='<i class="dot red"></i> API error'; console.error(e)}
}
function renderSkills(){
 const q=(document.getElementById('skillSearch')?.value||'').toLowerCase();
 const mode=document.getElementById('modeFilter')?.value||'';
 const list=state.skills.filter(s=>(!mode||s.mode===mode)&&((s.name+' '+s.description).toLowerCase().includes(q)));
 document.getElementById('skillGrid').innerHTML=list.map(s=>'<div class="skill"><div class="skilltop"><div><h3>'+esc(s.name.replaceAll('_',' '))+'</h3><p>'+esc(s.description)+'</p></div><span class="badge '+(s.mode==='approval'?'amber':s.mode==='read'?'green':'')+'">'+esc(s.mode)+'</span></div><button class="btn primary" onclick="openSkill(\''+esc(s.name)+'\')">Open skill</button></div>').join('')||'<div class="empty">No matching skills.</div>';
}
document.getElementById('skillSearch').oninput=renderSkills;document.getElementById('modeFilter').onchange=renderSkills;document.getElementById('jobSearch').oninput=filterJobs;document.getElementById('jobStatusFilter').onchange=filterJobs;document.getElementById('jobWorkplaceFilter').onchange=filterJobs;document.getElementById('jobScoreSort').onchange=filterJobs;

function openSkill(name){
 const s=state.skills.find(x=>x.name===name); if(!s)return;
 state.activeSkill=s;document.getElementById('drawer').classList.add('open');
 document.getElementById('drawerTitle').textContent=s.name.replaceAll('_',' ');
 document.getElementById('drawerDesc').textContent=s.description;
 document.getElementById('drawerSafety').innerHTML=s.mode==='approval'?'⚑ <b>Approval required.</b> This creates a review item; it does not execute the LinkedIn action.':s.mode==='read'?'✓ <b>Read-only.</b> This may open your local LinkedIn browser session and can take up to a few minutes.':'✦ <b>Local workflow.</b> No LinkedIn account action is performed automatically.';
 document.getElementById('skillFields').innerHTML=(s.fields||[]).map(f=>{
   const val=f.default??''; const type=f.type==='textarea'?'textarea':(f.type==='number'?'number':'text');
   return '<div class="field"><label>'+esc(f.label||f.name)+'</label>'+ (type==='textarea'?'<textarea name="'+esc(f.name)+'">'+esc(val)+'</textarea>':type==='select'?'<select name="'+esc(f.name)+'">'+(f.options||[]).map(o=>'<option value="'+esc(o)+'"'+(String(o)===String(val)?' selected':'')+'>'+esc(o)+'</option>').join('')+'</select>':'<input name="'+esc(f.name)+'" type="'+type+'" value="'+esc(val)+'">')+'</div>';
 }).join('') || '<p class="muted">No input required.</p>';
 document.getElementById('skillSubmit').textContent=s.mode==='approval'?'Prepare approval':(s.mode==='local'?'Run locally':'Run read-only skill');
 document.getElementById('skillTask').innerHTML='';document.getElementById('skillOutput').innerHTML='';
}
function closeDrawer(){document.getElementById('drawer').classList.remove('open')}
function scoreClass(v){
 const n=Number(v); return !Number.isFinite(n)?'':(n>=80?'high':n>=60?'mid':'low');
}
function prettyKey(k){return String(k||'').replaceAll('_',' ').replace(/\\b\\w/g,m=>m.toUpperCase())}
function resultLabel(k){
 return prettyKey(k).replace(/^(Url|Href)$/,'Link');
}
function resultValue(v){
 if(v==null||v==='') return '';
 if(typeof v==='boolean') return v?'Yes':'No';
 if(Array.isArray(v)) return v.map(resultValue).filter(Boolean).join(', ');
 if(typeof v==='object') return JSON.stringify(v);
 return String(v);
}
function resultHref(x){
 return x?.url||x?.href||x?.link||x?.job_url||x?.profile_url||x?.post_url||'';
}
function resultTitle(x){
 return x?.title||x?.job_title||x?.name||x?.company||x?.full_name||x?.person||'Result';
}
function resultMeta(x){
 return [x?.company,x?.location,x?.posted,x?.posted_hours!=null?(x.posted_hours+'h ago'):'',x?.workplace_type]
   .filter(v=>v!==undefined&&v!==null&&String(v).trim()).map(String).filter((v,i,a)=>a.indexOf(v)===i).join(' · ');
}
function renderResultCards(rows){
 return '<div class="result-cards">'+rows.map((x,i)=>{
   const href=resultHref(x), title=resultTitle(x), meta=resultMeta(x);
   const entries=Object.entries(x||{}).filter(([k,v])=>{
     const lk=k.toLowerCase();
     return v!==undefined&&v!==null&&v!==''&&!['url','href','link','job_url','profile_url','post_url','title','job_title','name','company','full_name','person','source','text'].includes(lk);
   }).slice(0,6);
   const text=x?.text||x?.description||x?.summary||'';
   return '<article class="result-card"><div class="result-card-top"><div class="result-card-main"><div class="result-card-title">'+(href?'<a href="'+esc(href)+'" target="_blank" rel="noopener noreferrer">'+esc(title)+'</a>':'<b>'+esc(title)+'</b>')+'</div>'+(meta?'<div class="result-card-meta">'+esc(meta)+'</div>':'')+'</div><div class="result-card-actions">'+(x?.easy_apply===true||String(x?.text||'').toLowerCase().includes('easy apply')?'<span class="badge green">Easy Apply</span>':'')+(href?'<a class="btn primary result-open" href="'+esc(href)+'" target="_blank" rel="noopener noreferrer">Open ↗</a>':'')+'</div></div>'+
   (text?'<div class="result-card-text">'+esc(String(text).slice(0,500))+'</div>':'')+
   (entries.length?'<div class="result-fields">'+entries.map(([k,v])=>'<div class="result-field"><span>'+esc(resultLabel(k))+'</span><b>'+esc(resultValue(v))+'</b></div>').join('')+'</div>':'')+
   '</article>';
 }).join('')+'</div>';
}
function renderObjectResult(result,data){
 if(data?.readable_result && (result?.skill==='profile_optimizer'||data?.skill==='profile_optimizer')){
   const p=data.readable_result, profile=p.profile||{}, audit=p.section_audit||{};
   const list=(v)=>Array.isArray(v)?v.filter(Boolean).map(x=>'<li>'+esc(typeof x==='object'?JSON.stringify(x):String(x))+'</li>').join(''):'';
   let h='<div class="result-shell"><div class="result-head"><div><div class="result-title">Profile Optimizer</div><div class="result-meta">'+esc(p.status||'Analysis completed')+'</div></div></div>';
   h+='<div class="result-message">'+esc(p.safety||'No LinkedIn profile changes were made.')+'</div>';
   h+='<div class="result-fields result-summary"><div class="result-field"><span>Name</span><b>'+esc(profile.name||'Not detected')+'</b></div><div class="result-field"><span>Headline</span><b>'+esc(profile.headline||'Not detected')+'</b></div><div class="result-field"><span>Location</span><b>'+esc(profile.location||'Not detected')+'</b></div></div>';
   h+='<div class="result-subhead">Profile Audit</div><div class="result-fields result-summary">'+Object.entries(audit).map(([k,v])=>'<div class="result-field"><span>'+esc(k)+'</span><b>'+esc(String(v))+'</b></div>').join('')+'</div>';
   if(p.assessment) h+='<div class="result-subhead">Assessment</div><div class="result-message">'+esc(p.assessment)+'</div>';
   const grounding=p.source_grounding||null;
   if(grounding){
     const publishable=grounding.publishable===true;
     const issues=Array.isArray(grounding.blocking_issues)?grounding.blocking_issues:[];
     const fields=grounding.fields&&typeof grounding.fields==='object'?grounding.fields:{};
     const badge=publishable?'<span class="badge green">✓ SOURCE-GROUNDED</span>':'<span class="badge red">⚠ BLOCKED — REVIEW REQUIRED</span>';
     h+='<div class="result-subhead">Source Grounding</div>';
     h+='<div class="result-message"><div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap">'+badge+'<span class="muted">'+esc(publishable?'No unsupported factual anchors detected.':'Unsupported factual anchors were detected. Do not publish these drafts until corrected.')+'</span></div></div>';
     const fieldRows=Object.entries(fields).map(([field,info])=>{
       const status=info?.status||'not_provided';
       const cls=status==='safe'?'green':status==='blocked'?'red':'amber';
       const label=status==='safe'?'Safe':status==='blocked'?'Blocked':'Not provided';
       return '<div class="result-field"><span>'+esc(prettyKey(field))+'</span><b><span class="badge '+cls+'">'+label+'</span></b></div>';
     }).join('');
     if(fieldRows) h+='<div class="result-fields result-summary">'+fieldRows+'</div>';
     if(issues.length){
       h+='<div class="result-message" style="margin-top:8px"><b>Blocking issues</b><ul class="result-list">'+issues.map(issue=>{
         const values=Array.isArray(issue.values)?' — '+issue.values.join(', '):'';
         return '<li>'+esc(prettyKey(issue.field||'field')+': '+String(issue.message||issue.type||'Unsupported claim')+values)+'</li>';
       }).join('')+'</ul></div>';
     }
   }
   if(p.ai_error) h+='<div class="error"><b>AI warning:</b> '+esc(p.ai_error)+'</div>';
   const sections=[['Headline Recommendations',p.headline_recommendations],['About Recommendation',p.about_recommendation],['Experience Recommendations',p.experience_recommendations],['Skills to Highlight',p.skills_to_highlight],['Featured Recommendations',p.featured_recommendations],['Strengths',p.strengths],['Missing Information',p.missing_information],['Next Actions',p.next_actions]];
   sections.forEach(([title,value])=>{ if(!value || (Array.isArray(value)&&!value.length)) return; h+='<div class="result-subhead">'+esc(title)+'</div>'; if(Array.isArray(value)) h+='<ul class="result-list">'+list(value)+'</ul>'; else h+='<div class="result-message">'+esc(String(value))+'</div>'; });
   return h+'</div>';
 }
 const entries=Object.entries(data||{}).filter(([k,v])=>v!==undefined&&v!==null&&v!=='');
 const message=data?.message||data?.details||data?.status;
 const arrays=entries.filter(([_,v])=>Array.isArray(v));
 const scalars=entries.filter(([_,v])=>!Array.isArray(v)&&!['diagnostics','data'].includes(_));
 let html='<div class="result-shell"><div class="result-head"><div><div class="result-title">Result</div><div class="result-meta">'+esc(result.skill?prettyKey(result.skill):'Completed successfully')+'</div></div></div>';
 if(message) html+='<div class="result-message">'+esc(resultValue(message))+'</div>';
 if(scalars.length){
   html+='<div class="result-fields result-summary">'+scalars.slice(0,8).map(([k,v])=>'<div class="result-field"><span>'+esc(resultLabel(k))+'</span><b>'+esc(resultValue(v))+'</b></div>').join('')+'</div>';
 }
 arrays.forEach(([k,v])=>{
   if(!v.length)return;
   const objects=v.filter(x=>x&&typeof x==='object');
   html+='<div class="result-subhead">'+esc(resultLabel(k))+' <span>'+esc(String(v.length))+'</span></div>';
   html+=objects.length?renderResultCards(objects):'<div class="result-message">'+esc(resultValue(v))+'</div>';
 });
 return html+'</div>';
}
function agentMetric(label,value,hint=''){
 return '<div class="agent-metric"><span>'+esc(label)+'</span><b>'+esc(value==null?'0':value)+'</b><small>'+esc(hint)+'</small></div>';
}
function formatDuration(seconds){
 const n=Number(seconds);
 if(!Number.isFinite(n))return '—';
 if(n<60)return Math.round(n)+' sec';
 const m=Math.floor(n/60), s=Math.round(n%60);
 return m+' min'+(s?' '+s+' sec':'');
}
function renderAgentJobs(rows){
 const jobs=(rows||[]).map(x=>x?.job||x).filter(x=>x&&typeof x==='object');
 if(!jobs.length)return '<div class="agent-empty">No matching jobs were found in this cycle.</div>';
 return '<div class="agent-job-list">'+jobs.slice(0,10).map(x=>{
   const href=x.url||x.href||'', title=x.title||'LinkedIn job', meta=[x.company,x.location,x.posted_text||x.posted].filter(Boolean).join(' · ');
   return '<div class="agent-job"><div><div class="agent-job-title">'+(href?'<a href="'+esc(href)+'" target="_blank" rel="noopener noreferrer">'+esc(title)+'</a>':'<b>'+esc(title)+'</b>')+'</div><div class="agent-job-meta">'+esc(meta)+'</div></div><div class="agent-job-actions">'+(x.easy_apply?'<span class="badge green">Easy Apply</span>':'')+(href?'<a class="btn primary result-open" href="'+esc(href)+'" target="_blank" rel="noopener noreferrer">Open ↗</a>':'')+'</div></div>';
 }).join('')+'</div>';
}
function renderAgentPosts(items){
 const posts=(items||[]).filter(x=>x&&typeof x==='object');
 if(!posts.length)return '<div class="agent-empty">No matching hiring posts were found.</div>';
 return '<div class="agent-post-list">'+posts.slice(0,6).map(item=>{
   const p=item.post||{}, href=p.profile_url||p.href||'', author=p.author||'Hiring signal', text=p.text||'', reasons=(item.reasons||[]).join(' · ');
   return '<div class="agent-post"><div class="agent-post-author">'+esc(author)+'</div><div class="agent-post-text">'+esc(String(text).slice(0,420))+'</div>'+(reasons?'<div class="agent-job-meta">'+esc(reasons)+'</div>':'')+(href?'<a class="btn" href="'+esc(href)+'" target="_blank" rel="noopener noreferrer">View profile ↗</a>':'')+'</div>';
 }).join('')+'</div>';
}
function renderAgentResult(result){
 const r=result||{}, d=r.diagnostics||{}, last=d.timings_seconds||{};
 const duration=last.cycle_total??null;
 const jobs=r.ranked_jobs||[];
 const posts=r.hiring_posts||[];
 const health='Successful';
 const cards='<div class="agent-summary-grid">'+
   agentMetric('Jobs found',r.jobs_found,'Discovered this cycle')+
   agentMetric('New jobs',r.new_jobs,'Not seen before')+
   agentMetric('Stale removed',(d.stale_jobs_removed??0),'Older than 6 hours')+
   agentMetric('Relevant jobs',jobs.length,'Ranked for your preferences')+
   agentMetric('Hiring signals',posts.length,'Relevant hiring posts')+
   agentMetric('Applications sent',0,'Agent never auto-applies')+
   agentMetric('Duration',formatDuration(duration),'Complete discovery cycle')+
   '</div>';
 const diagnostics='<details class="agent-tech"><summary>⚙ Technical diagnostics <span>Advanced</span></summary><pre>'+esc(JSON.stringify(d,null,2))+'</pre></details>';
 return '<div class="agent-result"><div class="agent-success"><div><span class="badge green">✓ '+health+'</span><h3>Discovery completed successfully</h3><p>Your LinkedIn discovery cycle finished. Review the opportunities below.</p></div><div class="agent-safe">🔒 No LinkedIn account actions were performed</div></div>'+
 cards+
 '<section class="agent-section"><div class="agent-section-head"><div><h3>Relevant jobs</h3><p>Jobs matching your current search preferences · posted within the last 6 hours.</p></div><span class="badge">'+esc(String(jobs.length))+'</span></div>'+renderAgentJobs(jobs)+'</section>'+
 '<section class="agent-section"><div class="agent-section-head"><div><h3>Hiring signals</h3><p>Public posts that matched your hiring criteria.</p></div><span class="badge">'+esc(String(posts.length))+'</span></div>'+renderAgentPosts(posts)+'</section>'+
 diagnostics+'</div>';
}
function renderResult(result){
 if(result==null)return '<div class="empty">No result returned.</div>';
 const data=result.data??result;
 if(Array.isArray(data)){
   if(!data.length)return '<div class="empty">No matching results found.</div>';
   return '<div class="result-shell"><div class="result-head"><div><div class="result-title">'+esc(result.skill==='jobs'?'Relevant jobs':'Results')+'</div><div class="result-meta">'+esc(result.count!=null?String(result.count)+' matches':'Showing '+data.length+' results')+'</div></div></div>'+renderResultCards(data.slice(0,50))+'</div>';
 }
 if(typeof data==='object') return renderObjectResult(result,data);
 return '<div class="result-shell"><div class="result-message">'+esc(String(data))+'</div></div>';
}
async function submitSkill(e){
 e.preventDefault(); const s=state.activeSkill;if(!s)return;
 const inputs={}; new FormData(e.target).forEach((v,k)=>inputs[k]=v);
 document.getElementById('skillSubmit').disabled=true;document.getElementById('skillTask').innerHTML='<div class="task"><b>Starting…</b><div class="progress"><i></i></div></div>';
 try{const d=await api('/api/skill',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({skill:s.name,inputs})}); watchTask(d.task_id,'skillTask','skillOutput');}
 catch(err){document.getElementById('skillTask').innerHTML='<div class="error">'+esc(err.message)+'</div>';document.getElementById('skillSubmit').disabled=false}
}
async function watchTask(id,box,out){
 const el=document.getElementById(box); const output=document.getElementById(out);
 const poll=async()=>{
  try{const d=await api('/api/tasks/'+id);
   if(d.status==='queued'||d.status==='running'){el.innerHTML='<div class="task"><b>'+esc(d.status==='queued'?'Queued — waiting for browser worker':'Running…')+'</b><div class="progress"><i></i></div><small class="muted">The page stays responsive while LinkedIn work runs in the background.</small></div>';setTimeout(poll,900);return}
   document.getElementById('skillSubmit').disabled=false;
   if(d.status==='completed'){el.innerHTML='<div class="task"><span class="badge green">Completed</span></div>';output.innerHTML=renderResult(d.result);refreshAll()}
   else{el.innerHTML='<div class="error">Failed: '+esc(d.error)+'</div>'}
  }catch(e){el.innerHTML='<div class="error">'+esc(e.message)+'</div>'}
 };poll();
}
async function startAgent(){
 try{const d=await api('/api/agent',{method:'POST'});showView('agent');document.getElementById('tasks').innerHTML='<div class="task"><b>Agent queued</b><div class="progress"><i></i></div></div>';watchAgent(d.task_id)}
 catch(e){document.getElementById('tasks').innerHTML='<div class="error">'+esc(e.message)+'</div>'}
}
async function watchAgent(id){
 const poll=async()=>{const d=await api('/api/tasks/'+id);const box=document.getElementById('tasks');
   if(d.status==='queued'||d.status==='running'){
     box.innerHTML='<div class="task"><span class="badge">'+esc(d.status)+'</span><div class="progress"><i></i></div><small class="muted">Browser worker is active. This dashboard remains responsive.</small></div>';
   }else if(d.status==='completed'){
     box.innerHTML=renderAgentResult(d.result);
   }else{box.innerHTML='<div class="error">Failed: '+esc(d.error||'Unknown error')+'</div>'}
   if(d.status==='queued'||d.status==='running')setTimeout(poll,1000);else refreshAll();
 };poll();
}
async function decide(id,approved){
 try{
   const result=await api('/api/approvals/'+encodeURIComponent(id),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approved})});
   if(result.task_id){
     showView('approvals');
     document.getElementById('approvalSummary').textContent='Approved. LinkedIn profile update is running through the safety-gated browser worker…';
     const poll=async()=>{
       try{
         const task=await api('/api/tasks/'+encodeURIComponent(result.task_id));
         if(task.status==='queued'||task.status==='running'){setTimeout(poll,900);return}
         if(task.status==='completed'){
           document.getElementById('approvalSummary').textContent='Profile update completed and verified. Refreshing approval history…';
         }else{
           document.getElementById('approvalSummary').textContent='Profile update failed safely. The approval remains recorded for audit.';
         }
         refreshAll();
       }catch(e){document.getElementById('approvalSummary').textContent='Profile update status could not be loaded.'}
     };
     poll();
   }else{
     refreshAll();
   }
 }catch(e){alert(e.message)}
}
async function transitionApplication(button){
 const select=button.closest('tr').querySelector('.statusSelect');
 const url=select.dataset.url; const status=select.value;
 button.disabled=true;
 try{
   await api('/api/applications/transition',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_url:url,status})});
   refreshAll();
 }catch(e){
   select.value=select.dataset.current||select.value;
   alert(e.message);
   button.disabled=false;
 }
}
function filterApplications(){
 const q=(document.getElementById('appSearch')?.value||'').toLowerCase().trim();
 const status=document.getElementById('appStatusFilter')?.value||'';
 document.querySelectorAll('#appsTable tbody tr').forEach((tr,i)=>{
   if(tr.classList.contains('app-details')) return;
   const text=tr.innerText.toLowerCase();
   const sel=tr.querySelector('.statusSelect');
   const ok=(!q||text.includes(q))&&(!status||sel?.value===status);
   tr.style.display=ok?'':'none';
   const detail=tr.nextElementSibling;if(detail?.classList.contains('app-details')) detail.style.display='none';
 });
}
function toggleAppDetails(button){
 const detail=button.closest('tr').nextElementSibling;
 if(detail) detail.classList.toggle('open');
}
async function saveApplicationDetails(button){
 const row=button.closest('tr'); const data={job_url:button.dataset.url};
 row.querySelectorAll('[data-field]').forEach(el=>data[el.dataset.field]=el.value);
 button.disabled=true;
 try{await api('/api/applications/details',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});refreshAll()}
 catch(e){alert(e.message);button.disabled=false}
}
function renderSystem(){
 const d=state.summary||{}, warnings=d.warnings||[], r=d.last_run||{};
 document.getElementById('systemDetails').innerHTML='<div class="system-grid">'+
   agentMetric('Skills',state.skills.length,'Registered')+
   agentMetric('Jobs tracked',d.jobs_tracked??0,'Local history')+
   agentMetric('Applications',d.application_count??0,'Pipeline')+
   agentMetric('Pending approvals',d.pending_approvals??0,'Human review')+
   '</div>'+
   '<div class="system-status"><span class="badge '+(warnings.length?'amber':'green')+'">'+(warnings.length?'Attention needed':'System healthy')+'</span><span>'+esc(warnings.length?warnings.length+' warning(s) detected':'No dashboard data warnings')+'</span></div>'+
   (warnings.length?'<details class="agent-tech"><summary>⚙ Warnings <span>Advanced</span></summary><pre>'+esc(JSON.stringify(warnings,null,2))+'</pre></details>':'')+
   '<details class="agent-tech"><summary>⚙ Technical diagnostics <span>Advanced</span></summary><pre>'+esc(JSON.stringify({last_run:r,activity_count:(d.activity||[]).length},null,2))+'</pre></details>';
}
document.getElementById('appSearch')?.addEventListener('input',filterApplications);
document.getElementById('appStatusFilter')?.addEventListener('change',filterApplications);
refreshAll();
</script>
</body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    server_version = "LinkedInAgentDashboard/2.0"

    def _send(self, status, payload, content_type="application/json; charset=utf-8"):
        raw = payload if isinstance(payload, bytes) else json.dumps(payload, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, _HTML.encode(), "text/html; charset=utf-8")
        elif path == "/api/health":
            self._send(200, {"ok": True, "service": "linkedin-agent-dashboard", "version": "2.0"})
        elif path == "/api/summary":
            try:
                self._send(200, _summary())
            except Exception as exc:
                self._send(500, {"error": f"{type(exc).__name__}: {exc}"})
        elif path == "/api/skills":
            self._send(200, {"skills": skill_catalog()})
        elif path.startswith("/api/tasks/"):
            task = _task_get(path.rsplit("/", 1)[-1])
            self._send(200 if task else 404, task or {"error": "task not found"})
        elif path == "/api/system":
            self._send(200, {"service":"linkedin-agent-dashboard","host":"127.0.0.1","port":self.server.server_address[1],"skills":len(skill_catalog()),"application_statuses":list(STATUSES),"version":"2.1"})
        elif path == "/api/activity":
            self._send(200, {"activity": _summary().get("activity", [])})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/skill":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = _read_json_body(self)
                name = str(body.get("skill", "")).strip()
                inputs = body.get("inputs") or {}
                task_id = _task_submit(
                    "skill:" + name,
                    lambda: asyncio.run(run_skill(name, inputs)),
                )
                self._send(202, {"task_id": task_id, "status": "queued", "skill": name})
            except Exception as exc:
                self._send(400, {"error": f"{type(exc).__name__}: {exc}"})
            return
        if path == "/api/agent":
            try:
                if _has_active_task("agent"):
                    self._send(409, {"error": "An agent run is already queued or running."})
                    return
                from .daily_agent import run_agent_once
                task_id = _task_submit("agent", lambda: asyncio.run(run_agent_once(max_posted_hours=6)))
                self._send(202, {"task_id": task_id, "status": "queued"})
            except Exception as exc:
                self._send(400, {"error": f"{type(exc).__name__}: {exc}"})
            return
        if path == "/api/applications/add":
            try:
                body = _read_json_body(self)
                from .application_tracker import ApplicationTracker
                added = ApplicationTracker().add(
                    body.get("job_url",""), body.get("title",""), body.get("company",""),
                    "new", source=body.get("source","LinkedIn"), location=body.get("location","")
                )
                self._send(200, {"added": bool(added), "job_url": str(body.get("job_url","")).strip()})
            except ValueError as exc:
                self._send(400, {"error": str(exc)})
            except Exception as exc:
                self._send(500, {"error": f"{type(exc).__name__}: {exc}"})
            return
        if path == "/api/applications/details":
            try:
                body = _read_json_body(self)
                job_url = str(body.get("job_url", "")).strip()
                allowed = {"source","location","recruiter","resume_version","next_follow_up","interview_date","salary_notes","notes","applied_at","discovered_at"}
                fields = {k: body.get(k) for k in allowed if k in body}
                from .application_tracker import ApplicationTracker
                ApplicationTracker().update_details(job_url, **fields)
                self._send(200, {"changed": True, "job_url": job_url})
            except KeyError:
                self._send(404, {"error": "Application not found"})
            except ValueError as exc:
                self._send(400, {"error": str(exc)})
            except Exception as exc:
                self._send(500, {"error": f"{type(exc).__name__}: {exc}"})
            return
        if path == "/api/applications/transition":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length) or b"{}")
                job_url = str(body.get("job_url", "")).strip()
                status = str(body.get("status", "")).strip()
                if status not in STATUSES:
                    raise ValueError("Invalid application status")
                changed = ApplicationTracker().transition(job_url, status)
                self._send(200, {"changed": bool(changed), "job_url": job_url, "status": status})
            except KeyError:
                self._send(404, {"error": "Application not found"})
            except ValueError as exc:
                self._send(400, {"error": str(exc)})
            except Exception as exc:
                self._send(500, {"error": f"{type(exc).__name__}: {exc}"})
            return
        if path.startswith("/api/approvals/"):
            item_id = path.rsplit("/", 1)[-1]
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length) or b"{}")
                from .approval_queue import ApprovalQueue
                from .telegram_notify import notify_profile_optimization_apply
                queue = ApprovalQueue()
                approved = _parse_approval_decision(body.get("approved", False))
                item = queue.get(item_id)
                if item is None or item.status != "pending":
                    self._send(404, {"error": "approval item is missing or already decided"})
                    return
                changed = queue.decide(item_id, approved)
                response = {"changed": changed, "approved": approved}
                if changed and approved and item.action == "profile_optimization_review":
                    proposal = json.loads(item.payload)
                    def apply_profile():
                        try:
                            from .profile_writer import apply_approved_profile_proposal
                            result = asyncio.run(apply_approved_profile_proposal(proposal))
                            queue.mark_applied(item_id)
                            notify_profile_optimization_apply(
                                success=True,
                                review_id=item_id,
                                applied=result.get("applied", []),
                                verified=result.get("verified", []),
                                skipped=result.get("skipped", []),
                            )
                            return result
                        except Exception as exc:
                            queue.mark_apply_failed(item_id, str(exc))
                            notify_profile_optimization_apply(
                                success=False,
                                review_id=item_id,
                                error_message=f"{type(exc).__name__}: {exc}",
                            )
                            raise
                    response["task_id"] = _task_submit("profile-apply", apply_profile)
                    response["status"] = "queued"
                self._send(200, response)
            except Exception as exc:
                self._send(400, {"error": str(exc)})
            return
        self._send(404, {"error":"not found"})

    def log_message(self, fmt, *args):
        return


def serve(host="127.0.0.1", port=8765):
    try:
        server = ThreadingHTTPServer((host, port), _Handler)
    except OSError as exc:
        raise SystemExit(
            f"dashboard: cannot bind http://{host}:{port} ({exc}). "
            "Another process may be using the port. Try: "
            "python -m app dashboard --port 8766"
        ) from exc
    print(f"dashboard: http://{host}:{port}")
    print("LinkedIn Agent Control Center 2.0")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
