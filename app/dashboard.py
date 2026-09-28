from __future__ import annotations

import asyncio
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
from .application_tracker import ApplicationTracker, STATUSES


# One worker prevents two Playwright sessions from competing for the same
# persistent LinkedIn profile. The HTTP server itself remains responsive.
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="linkedin-dashboard")
_TASKS: dict[str, dict] = {}
_TASK_LOCK = threading.Lock()
_MAX_TASKS = 100


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


def _task_get(task_id: str) -> dict | None:
    with _TASK_LOCK:
        item = _TASKS.get(task_id)
        return dict(item) if item else None


def _db(path: str):
    con = sqlite3.connect(path, timeout=2.0)
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
            rows = db.execute(
                "SELECT job_url,title,company,status,updated_at,notes FROM applications "
                "ORDER BY updated_at DESC LIMIT 50"
            ).fetchall()
            return count, [
                {
                    **dict(r),
                    "allowed_transitions": sorted(TRANSITIONS.get(r["status"], set())),
                }
                for r in rows
            ]

    def load_jobs():
        with _db(activity) as db:
            count = db.execute("SELECT COUNT(*) FROM job_history").fetchone()[0]
            rows = db.execute(
                "SELECT title,company,location,url,score,reasons,status,first_seen "
                "FROM job_history ORDER BY id DESC LIMIT 50"
            ).fetchall()
            out = []
            for r in rows:
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
.main{margin-left:248px;width:calc(100% - 248px);padding:24px 30px 48px}.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px}
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
.result-shell{margin-top:14px}.result-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px}.result-title{font-size:15px;font-weight:800}.result-meta{font-size:11px;color:var(--muted);margin-top:2px}.result-actions{display:flex;gap:7px;flex-wrap:wrap}.result-table{max-height:480px}.result-table .table th{position:sticky;top:0;background:#0c1b2d;z-index:1}.result-list{display:grid;gap:8px;max-height:480px;overflow:auto}.result-job{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:13px 14px;background:rgba(255,255,255,.035);border:1px solid var(--line);border-radius:10px}.result-job-main{min-width:0}.result-job-title{font-size:13px;font-weight:800}.result-job-title a{color:#9ed8ff;text-decoration:none}.result-job-title a:hover{text-decoration:underline}.result-job-meta{font-size:11px;color:var(--muted);margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.result-job-actions{display:flex;align-items:center;gap:7px;flex:0 0 auto}.result-open{padding:7px 10px;white-space:nowrap}.score{display:inline-flex;min-width:38px;justify-content:center;padding:4px 7px;border-radius:8px;font-weight:850;font-size:11px;background:rgba(72,168,255,.12);color:#9ed8ff}.score.high{background:rgba(50,213,131,.11);color:#7af0b0}.score.mid{background:rgba(253,176,34,.11);color:#ffd27a}.score.low{background:rgba(249,112,102,.10);color:#ffaaa3}.run-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px}.run-chip{padding:10px;border-radius:10px;background:rgba(255,255,255,.035);border:1px solid var(--line)}.run-chip b{display:block;font-size:16px}.run-chip span{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}.section-kicker{font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:#6f87a0;font-weight:800;margin-bottom:5px}.nav-section{font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:#526a83;padding:16px 12px 5px;font-weight:800}.live-pill{display:inline-flex;align-items:center;gap:6px;padding:5px 9px;border-radius:999px;background:rgba(50,213,131,.08);border:1px solid rgba(50,213,131,.16);color:#7be9ae;font-size:10px;font-weight:800}.live-pill i{width:6px;height:6px;border-radius:50%;background:currentColor}.drawerbox{width:min(760px,96vw)}.table td{font-size:12px}.table th{white-space:nowrap}@media(max-width:650px){.result-head{flex-direction:column}.drawerbox{width:100%}}
.tablewrap{overflow:auto}.table{width:100%;border-collapse:collapse}.table th{font-size:11px;text-transform:uppercase;color:#7890aa;letter-spacing:.04em;text-align:left;padding:10px 8px;border-bottom:1px solid var(--line)}.table td{padding:11px 8px;border-bottom:1px solid rgba(154,181,211,.09);vertical-align:top}.table tr:hover td{background:rgba(72,168,255,.035)}
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
  <div class="actions"><span id="health" class="health"><i class="dot"></i> Checking</span><span class="live-pill"><i></i> READ-ONLY · 2H CADENCE</span><button class="btn" onclick="refreshAll()">↻ Refresh</button><button class="btn primary" onclick="startAgent()">Run Agent</button></div>
</header>

<section id="overview" class="view active">
  <div class="grid metrics" id="metrics"></div>
  <div class="hero"><div class="section-kicker" style="color:#9bd6ff">COMMAND CENTER</div><h2>Discover opportunities. Review signals. Stay in control.</h2><p>The agent continuously discovers jobs and hiring signals while keeping account-changing actions behind human approval. Use the workspace below to review results, manage your pipeline and launch individual skills.</p><div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" onclick="showView('jobs')">Review jobs →</button><button class="btn" onclick="showView('skills')">Open Skill Center →</button></div></div>
  <div class="grid quick">
    <button onclick="openSkill('jobs')"><b>Find Power BI jobs</b><span>LinkedIn · Delhi / Gurgaon / Noida / Remote India</span></button>
    <button onclick="openSkill('people')"><b>Find recruiters</b><span>People research · read-only</span></button>
    <button onclick="openSkill('posts')"><b>Find hiring posts</b><span>Content search · read-only</span></button>
    <button onclick="openSkill('post_writer')"><b>Write a LinkedIn post</b><span>Local drafting · approval before publish</span></button>
  </div>
  <div class="grid two" style="margin-top:16px">
    <div class="card"><div class="cardhead"><div><h2>Recent jobs</h2><p>Latest records stored locally</p></div><button class="btn" onclick="showView('jobs')">View all</button></div><div class="tablewrap"><table class="table" id="overviewJobs"></table></div></div>
    <div class="card"><div class="cardhead"><div><h2>Last agent run</h2><p id="runMeta">Loading…</p></div></div><pre id="lastRun"></pre></div>
  </div>
</section>

<section id="skills" class="view">
  <div class="card">
    <div class="cardhead"><div><h2>Skill Center</h2><p>All registered skills, using the repository's real skill adapters.</p></div></div>
    <div class="toolbar"><input class="search" id="skillSearch" placeholder="Search skills, e.g. recruiter, post, humanizer…"><select id="modeFilter"><option value="">All modes</option><option value="read">Read</option><option value="local">Draft / Analyze</option><option value="approval">Approval</option></select></div>
    <div class="grid skills" id="skillGrid"></div>
  </div>
</section>

<section id="jobs" class="view"><div class="card"><div class="cardhead"><div><h2>Job Intelligence</h2><p>Stored discovery history and application signals.</p></div><button class="btn primary" onclick="openSkill('jobs')">Search LinkedIn jobs</button></div><div class="toolbar"><input class="search" id="jobSearch" placeholder="Search role, company, location…"><select id="jobStatusFilter"><option value="">All statuses</option><option value="new">New</option><option value="shortlisted">Shortlisted</option><option value="drafted">Drafted</option><option value="applied">Applied</option><option value="screening">Screening</option><option value="interview">Interview</option><option value="offer">Offer</option><option value="rejected">Rejected</option><option value="withdrawn">Withdrawn</option><option value="closed">Closed</option></select><select id="jobWorkplaceFilter"><option value="">All workplace types</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="on-site">On-site</option></select></div><div class="tablewrap"><table class="table" id="jobsTable"></table></div></div></section>
<section id="applications" class="view">
<div class="card"><div class="cardhead"><div><h2>Application Pipeline</h2><p>Local application tracking with governed status transitions.</p></div></div>
<div class="tablewrap"><table class="table" id="appsTable"></table></div></div>
</section>
<section id="approvals" class="view"><div class="card"><div class="cardhead"><div><h2>Approval Queue</h2><p>Nothing is sent or published automatically.</p></div></div><div class="tablewrap"><table class="table" id="approvalTable"></table></div></div></section>
<section id="agent" class="view">
<div class="grid two">
 <div class="card"><div class="cardhead"><div><h2>Agent Runs</h2><p>Run the complete governed discovery cycle.</p></div><button class="btn primary" onclick="startAgent()">Run Agent Now</button></div><div id="tasks"></div></div>
 <div class="card"><div class="cardhead"><div><h2>Last run details</h2><p>Persisted health state and diagnostics.</p></div></div><pre id="agentDetails"></pre></div>
</div>
<div class="card" style="margin-top:15px"><div class="cardhead"><div><h2>Recent activity</h2><p>Local audit trail from the application database.</p></div></div><div class="tablewrap"><table class="table" id="activityTable"></table></div></div>
</section>
<section id="system" class="view"><div class="grid three"><div class="card"><h2>Safety</h2><p class="muted">Read-only LinkedIn discovery is automatic. Account-changing workflows remain approval-gated.</p></div><div class="card"><h2>Browser</h2><p class="muted">Uses your persistent local Playwright profile. Credentials remain on your machine.</p></div><div class="card"><h2>Performance</h2><p class="muted">Dashboard requests return immediately for long-running skills and poll for completion.</p></div></div><div class="card" style="margin-top:14px"><h2>System diagnostics</h2><pre id="systemDetails"></pre></div></section>
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
 return '<thead><tr><th>Role</th><th>Company</th><th>Location</th><th>Workplace</th><th>Score</th><th>Status</th><th>Seen</th></tr></thead><tbody>'+
 (list.length ? list.map(x=>{
   const link=x.url?'<a href="'+esc(x.url)+'" target="_blank" rel="noopener noreferrer" style="color:#8dccff;text-decoration:none">'+esc(x.title)+'</a>':'<b>'+esc(x.title)+'</b>';
   const wp=x.workplace_type||((String(x.location||'').toLowerCase().includes('remote'))?'remote':'');
   const reason=String(x.reasons||'').slice(0,180);
   return '<tr><td><b>'+link+'</b>'+(reason?'<div class="muted" style="font-size:11px;margin-top:3px">'+esc(reason)+'</div>':'')+'</td><td>'+esc(x.company)+'</td><td>'+esc(x.location)+'</td><td>'+(wp?'<span class="badge green">'+esc(wp)+'</span>':'<span class="muted">—</span>')+'</td><td>'+esc(x.score??'—')+'</td><td><span class="badge">'+esc(x.status||'new')+'</span></td><td>'+esc(x.updated_at)+'</td></tr>';
 }).join('') : '<tr><td colspan="7" class="empty">No jobs stored yet.</td></tr>')+
 '</tbody>';
}
function filterJobs(){
 const q=(document.getElementById('jobSearch')?.value||'').toLowerCase().trim();
 const status=document.getElementById('jobStatusFilter')?.value||'';
 const workplace=document.getElementById('jobWorkplaceFilter')?.value||'';
 const rows=(state.summary?.jobs||[]).filter(x=>{
   const hay=[x.title,x.company,x.location,x.reasons].join(' ').toLowerCase();
   const wp=(x.workplace_type||((String(x.location||'').toLowerCase().includes('remote'))?'remote':'')).toLowerCase();
   return (!q||hay.includes(q))&&(!status||x.status===status)&&(!workplace||wp===workplace);
 });
 document.getElementById('jobsTable').innerHTML=jobRows(rows);
}
function renderTables(d){
 document.getElementById('jobsTable').innerHTML=jobRows(d.jobs);
 filterJobs();
 document.getElementById('overviewJobs').innerHTML=jobRows((d.jobs||[]).slice(0,8));
 document.getElementById('appsTable').innerHTML='<thead><tr><th>Role</th><th>Company</th><th>Status</th><th>Updated</th><th></th></tr></thead><tbody>'+
 (d.applications||[]).map(x=>'<tr><td><b>'+esc(x.title)+'</b></td><td>'+esc(x.company)+'</td><td><select class="statusSelect" data-url="'+esc(x.job_url)+'" data-current="'+esc(x.status)+'">'+[x.status,...(x.allowed_transitions||[])].filter((v,i,a)=>a.indexOf(v)===i).map(s=>'<option value="'+esc(s)+'" '+(s===x.status?'selected':'')+'>'+esc(s)+'</option>').join('')+'</select></td><td>'+esc(x.updated_at)+'</td><td><button class="btn" onclick="transitionApplication(this)">Save</button></td></tr>').join('')+'</tbody>';
 document.getElementById('activityTable').innerHTML='<thead><tr><th>Time</th><th>Action</th><th>Target</th><th>Status</th><th>Details</th></tr></thead><tbody>'+
 (d.activity||[]).map(x=>'<tr><td>'+esc(x.created_at)+'</td><td>'+esc(x.action)+'</td><td>'+esc(x.target)+'</td><td><span class="badge">'+esc(x.status)+'</span></td><td>'+esc(x.details)+'</td></tr>').join('')+'</tbody>';
 document.getElementById('approvalTable').innerHTML='<thead><tr><th>Action</th><th>Target</th><th>Status</th><th>Created</th><th></th></tr></thead><tbody>'+
 (d.approvals||[]).map(x=>'<tr><td>'+esc(x.action)+'</td><td>'+esc(x.target)+'</td><td><span class="badge amber">pending</span></td><td>'+esc(x.created_at)+'</td><td><button class="btn primary" onclick="decide(\''+esc(x.id)+'\',true)">Approve</button> <button class="btn" onclick="decide(\''+esc(x.id)+'\',false)">Reject</button></td></tr>').join('')+
 '</tbody>';
}
function renderRun(d){
 document.getElementById('lastRun').textContent=JSON.stringify(d.last_run||{},null,2);
 document.getElementById('agentDetails').textContent=JSON.stringify(d.last_run||{},null,2);
 document.getElementById('runMeta').textContent=(d.last_run?.last_finished_at||d.last_run?.updated_at||'No run recorded');
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
document.getElementById('skillSearch').oninput=renderSkills;document.getElementById('modeFilter').onchange=renderSkills;document.getElementById('jobSearch').oninput=filterJobs;document.getElementById('jobStatusFilter').onchange=filterJobs;document.getElementById('jobWorkplaceFilter').onchange=filterJobs;

function openSkill(name){
 const s=state.skills.find(x=>x.name===name); if(!s)return;
 state.activeSkill=s;document.getElementById('drawer').classList.add('open');
 document.getElementById('drawerTitle').textContent=s.name.replaceAll('_',' ');
 document.getElementById('drawerDesc').textContent=s.description;
 document.getElementById('drawerSafety').innerHTML=s.mode==='approval'?'⚑ <b>Approval required.</b> This creates a review item; it does not execute the LinkedIn action.':s.mode==='read'?'✓ <b>Read-only.</b> This may open your local LinkedIn browser session and can take up to a few minutes.':'✦ <b>Local workflow.</b> No LinkedIn account action is performed automatically.';
 document.getElementById('skillFields').innerHTML=(s.fields||[]).map(f=>{
   const val=f.default??''; const type=f.type==='textarea'?'textarea':(f.type==='number'?'number':'text');
   return '<div class="field"><label>'+esc(f.label||f.name)+'</label>'+ (type==='textarea'?'<textarea name="'+esc(f.name)+'">'+esc(val)+'</textarea>':'<input name="'+esc(f.name)+'" type="'+type+'" value="'+esc(val)+'">')+'</div>';
 }).join('') || '<p class="muted">No input required.</p>';
 document.getElementById('skillSubmit').textContent=s.mode==='approval'?'Prepare approval':(s.mode==='local'?'Run locally':'Run read-only skill');
 document.getElementById('skillTask').innerHTML='';document.getElementById('skillOutput').innerHTML='';
}
function closeDrawer(){document.getElementById('drawer').classList.remove('open')}
function scoreClass(v){
 const n=Number(v); return !Number.isFinite(n)?'':(n>=80?'high':n>=60?'mid':'low');
}
function prettyKey(k){return String(k||'').replaceAll('_',' ').replace(/\\b\\w/g,m=>m.toUpperCase())}
function renderJobResults(result,data){
 const rows=(data||[]).filter(x=>x&&typeof x==='object');
 if(!rows.length)return '<div class="empty">No matching jobs found.</div>';
 return '<div class="result-shell"><div class="result-head"><div><div class="result-title">Relevant jobs</div><div class="result-meta">'+esc(result.count!=null?String(result.count)+' matches':'Showing '+rows.length+' matches')+'</div></div></div><div class="result-list">'+rows.slice(0,50).map(x=>{
   const href=x.url||x.href||'';
   const title=x.title||x.job_title||'LinkedIn job';
   const company=x.company||'';
   const location=x.location||'';
   const posted=x.posted||'';
   const easy=x.easy_apply===true||String(x.text||'').toLowerCase().includes('easy apply');
   return '<div class="result-job"><div class="result-job-main"><div class="result-job-title">'+(href?'<a href="'+esc(href)+'" target="_blank" rel="noopener noreferrer">'+esc(title)+'</a>':'<b>'+esc(title)+'</b>')+'</div><div class="result-job-meta">'+esc(company)+(company&&location?' · ':'')+esc(location)+(posted?' · '+esc(posted):'')+'</div></div><div class="result-job-actions">'+(easy?'<span class="badge green">Easy Apply</span>':'')+(href?'<a class="btn primary result-open" href="'+esc(href)+'" target="_blank" rel="noopener noreferrer">Open job ↗</a>':'')+'</div></div>';
 }).join('')+'</div></div>';
}
function renderLinkedResults(result,data){
 const rows=(data||[]).filter(x=>x&&typeof x==='object'&&(x.url||x.href));
 if(!rows.length)return null;
 return '<div class="result-shell"><div class="result-head"><div><div class="result-title">Relevant links</div><div class="result-meta">Direct links from the selected skill</div></div></div><div class="result-list">'+rows.slice(0,50).map(x=>{
   const href=x.url||x.href;
   const title=x.title||x.name||x.job_title||'Open result';
   const meta=[x.company,x.location,x.posted].filter(Boolean).join(' · ');
   return '<div class="result-job"><div class="result-job-main"><div class="result-job-title"><a href="'+esc(href)+'" target="_blank" rel="noopener noreferrer">'+esc(title)+'</a></div><div class="result-job-meta">'+esc(meta)+'</div></div><a class="btn primary result-open" href="'+esc(href)+'" target="_blank" rel="noopener noreferrer">Open ↗</a></div>';
 }).join('')+'</div></div>';
}
function renderResult(result){
 if(result==null)return '<div class="empty">No result returned.</div>';
 const data=result.data??result;
 if(Array.isArray(data)){
   if(!data.length)return '<div class="empty">No matching records found.</div>';
   if(result.skill==='jobs')return renderJobResults(result,data);
   const linked=renderLinkedResults(result,data);
   if(linked)return linked;
   return '<div class="result-shell"><div class="result-head"><div><div class="result-title">Results</div><div class="result-meta">'+esc(result.count!=null?String(result.count)+' records':'Showing '+data.length+' records')+'</div></div></div><div class="result-list"><div class="result-job"><div class="result-job-main"><div class="result-job-title">Results available</div><div class="result-job-meta">Open the relevant section of the dashboard to review the structured records.</div></div></div></div></div>';
 }
 return '<div class="result-shell"><div class="result-head"><div><div class="result-title">Completed</div><div class="result-meta">The skill finished successfully.</div></div></div></div>';
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
     box.innerHTML='<div class="task"><span class="badge green">Completed</span><div class="muted" style="margin-top:6px">Discovery cycle finished successfully.</div></div>'+renderResult(d.result);
   }else{box.innerHTML='<div class="error">Failed: '+esc(d.error||'Unknown error')+'</div>'}
   if(d.status==='queued'||d.status==='running')setTimeout(poll,1000);else refreshAll();
 };poll();
}
async function decide(id,approved){
 try{await api('/api/approvals/'+encodeURIComponent(id),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approved})});refreshAll()}catch(e){alert(e.message)}
}
async function transitionApplication(button){
 const select=button.closest('tr').querySelector('.statusSelect');
 const url=select.dataset.url; const status=select.value;
 button.disabled=true;
 try{
   await api('/api/applications/transition',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_url:url,status})});
   refreshAll();
 }catch(e){alert(e.message);button.disabled=false}
}
function renderSystem(){document.getElementById('systemDetails').textContent=JSON.stringify({
 skills:state.skills.length,
 warnings:state.summary?.warnings||[],
 last_run:state.summary?.last_run||{},
 activity_count:(state.summary?.activity||[]).length
},null,2)}
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
                body = json.loads(self.rfile.read(length) or b"{}")
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
                from .daily_agent import run_agent_once
                task_id = _task_submit("agent", lambda: asyncio.run(run_agent_once()))
                self._send(202, {"task_id": task_id, "status": "queued"})
            except Exception as exc:
                self._send(400, {"error": f"{type(exc).__name__}: {exc}"})
            return
        if path == "/api/applications/transition":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length) or b"{}")
                job_url = str(body.get("job_url", "")).strip()
                status = str(body.get("status", "")).strip()
                if status not in STATUSES:
                    raise ValueError("Invalid application status")
                ApplicationTracker().transition(job_url, status)
                self._send(200, {"changed": True, "job_url": job_url, "status": status})
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
                changed = ApprovalQueue().decide(item_id, bool(body.get("approved", False)))
                self._send(200 if changed else 404, {"changed": changed})
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
