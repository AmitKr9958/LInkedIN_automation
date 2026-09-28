from __future__ import annotations

import asyncio
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .config import ROOT
from .run_status import read_run_status

_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LinkedIn Agent Control Center</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;background:#f6f7f9;color:#17202a}
header{background:#17202a;color:#fff;padding:18px 24px}main{max-width:1200px;margin:24px auto;padding:0 16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.card{background:#fff;border:1px solid #ddd;border-radius:10px;padding:16px;margin-bottom:16px}
button{border:0;border-radius:7px;padding:9px 13px;cursor:pointer;margin:4px}.primary{background:#0a66c2;color:#fff}.danger{background:#b42318;color:#fff}
pre{white-space:pre-wrap;max-height:420px;overflow:auto;background:#101828;color:#e6edf3;padding:14px;border-radius:8px}
table{width:100%;border-collapse:collapse;background:#fff}td,th{padding:9px;border-bottom:1px solid #eee;text-align:left}
.small{color:#667085;font-size:13px}.err{color:#b42318;background:#fff4f2;border:1px solid #f5c2c0}
</style></head><body><header><strong>LinkedIn Agent Control Center</strong>
<div class="small" style="color:#d0d5dd">Local-only · read/draft/approval governed · http://127.0.0.1:8765</div></header><main>
<div id="booterr" class="card err" style="display:none"></div>
<div class="grid" id="stats"></div>
<div class="card"><h2>Last agent run</h2><pre id="lastrun">Loading…</pre></div>
<div class="card"><h2>Quick actions</h2>
<p class="small">These are read-only LinkedIn skills. Choose an action, then review the result here. No messages, connections, likes, comments, or publishing are performed.</p>
<button class="primary" onclick="runSkill('jobs','Power BI','Gurgaon')">Find Power BI jobs</button>
<button onclick="runSkill('profile','','')">Read my profile</button>
<button onclick="runSkill('posts','Power BI','')">Find Power BI posts</button>
<button onclick="runSkill('people','Power BI recruiter','')">Find recruiters</button>
<button onclick="runSkill('companies','data analytics','')">Find companies</button>
<button onclick="runSkill('saved','','')">Read saved items</button>
<button onclick="runSkill('notifications','','')">Read notifications</button>
</div>
<div class="card"><h2>Agent</h2>
<p class="small">The Agent is the scheduled read-only workflow. Use this for the complete discovery cycle.</p>
<button class="primary" onclick="runAgent()">Run Agent Now</button>
<button onclick="refresh()">Refresh</button><span id="status" class="small"></span><pre id="agent">No run yet.</pre></div>
<div class="card"><h2>Skill result</h2><pre id="skillresult">Choose a Quick action above.</pre></div>
<div class="card"><h2>Pending approvals</h2><div style="overflow:auto"><table><thead><tr><th>Action</th><th>Target</th><th>Created</th><th></th></tr></thead><tbody id="approvals"></tbody></table></div></div>
<div class="card"><h2>Applications</h2><div style="overflow:auto"><table><thead><tr><th>Title</th><th>Company</th><th>Status</th><th>Updated</th></tr></thead><tbody id="applications"></tbody></table></div></div>
<div class="card"><h2>Recent jobs</h2><div style="overflow:auto"><table><thead><tr><th>Title</th><th>Company</th><th>Status</th><th>Updated</th></tr></thead><tbody id="jobs"></tbody></table></div></div>
</main><script>
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function api(path,opts){
  const ctrl=new AbortController();
  const timer=setTimeout(()=>ctrl.abort(),15000);
  let r;
  try{
    r=await fetch(path,Object.assign({signal:ctrl.signal},opts||{}));
  }catch(e){
    clearTimeout(timer);
    if(e.name==='AbortError') throw new Error('Request timed out: '+path);
    throw new Error('Cannot reach dashboard API ('+path+'). Is the server running?');
  }
  clearTimeout(timer);
  const text=await r.text();
  let d={};
  try{ d=text?JSON.parse(text):{}; }catch(_){ d={error:text||r.statusText}; }
  if(!r.ok) throw new Error(d.error||r.statusText||('HTTP '+r.status));
  return d;
}
async function refresh(){
  const boot=document.getElementById('booterr');
  const status=document.getElementById('status');
  try{
    const d=await api('/api/summary');
    boot.style.display='none';
    document.getElementById('stats').innerHTML=[
      ['Jobs tracked',d.jobs_tracked],
      ['Applications',d.application_count],
      ['Pending approvals',d.pending_approvals],
      ['Recent jobs',d.recent_jobs],
      ['Health',(d.last_run&&d.last_run.health_state)||(d.last_run&&d.last_run.last_status)||'—']
    ].map(x=>'<div class="card"><div class="small">'+esc(x[0])+'</div><h2>'+esc(x[1])+'</h2></div>').join('');
    document.getElementById('lastrun').textContent=JSON.stringify(d.last_run||{},null,2);
    document.getElementById('approvals').innerHTML=(d.approvals||[]).map(x=>'<tr><td>'+esc(x.action)+'</td><td>'+esc(x.target)+'</td><td>'+esc(x.created_at)+'</td><td><button class="primary" onclick="decide(\\''+x.id+'\\',true)">Approve</button><button class="danger" onclick="decide(\\''+x.id+'\\',false)">Reject</button></td></tr>').join('')||'<tr><td colspan="4">No pending approvals</td></tr>';
    document.getElementById('applications').innerHTML=(d.applications||[]).map(x=>'<tr><td>'+esc(x.title)+'</td><td>'+esc(x.company)+'</td><td>'+esc(x.status)+'</td><td>'+esc(x.updated_at)+'</td></tr>').join('')||'<tr><td colspan="4">None</td></tr>';
    document.getElementById('jobs').innerHTML=(d.jobs||[]).map(x=>'<tr><td>'+esc(x.title)+'</td><td>'+esc(x.company)+'</td><td>'+esc(x.status)+'</td><td>'+esc(x.updated_at)+'</td></tr>').join('')||'<tr><td colspan="4">None</td></tr>';
    if(d.warnings&&d.warnings.length){ status.textContent=' Warnings: '+d.warnings.join('; '); }
  }catch(e){
    boot.style.display='block';
    boot.textContent='Dashboard error: '+e.message;
    document.getElementById('lastrun').textContent='Failed to load: '+e.message;
  }
}
async function decide(id,approved){
  await api('/api/approvals/'+encodeURIComponent(id),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approved})});
  refresh();
}
async function runSkill(skill,query,location){
  const s=document.getElementById('status');
  const out=document.getElementById('skillresult');
  s.textContent=' Running '+skill+'…';
  out.textContent='Loading…';
  try{
    const d=await api('/api/skill',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({skill,query,location})});
    out.textContent=JSON.stringify(d,null,2);
    s.textContent=' Completed';
  }catch(e){ out.textContent='Failed: '+e.message; s.textContent=' Failed'; }
}
async function runAgent(){
  const s=document.getElementById('status');
  s.textContent=' Running read-only discovery…';
  try{
    const d=await api('/api/agent',{method:'POST'});
    document.getElementById('agent').textContent=JSON.stringify(d,null,2);
    s.textContent=' Completed';
    refresh();
  }catch(e){ s.textContent=' Failed: '+e.message; }
}
refresh();
</script></body></html>
"""


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
            # Table may not exist yet on a fresh install.
            rows = db.execute(
                "SELECT id,action,target,payload,status,created_at FROM approval_queue "
                "WHERE status='pending' ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
            return [dict(r) for r in rows]

    def load_applications():
        with _db(activity) as db:
            rows = db.execute(
                "SELECT job_url,title,company,status,updated_at,notes FROM applications "
                "ORDER BY updated_at DESC LIMIT 20"
            ).fetchall()
            return [dict(r) for r in rows]

    def load_jobs():
        with _db(activity) as db:
            rows = db.execute(
                "SELECT title,company,location,url,score,reasons,status,first_seen "
                "FROM job_history ORDER BY id DESC LIMIT 20"
            ).fetchall()
            out = []
            for r in rows:
                out.append(
                    {
                        "title": r["title"],
                        "company": r["company"],
                        "location": r["location"],
                        "url": r["url"],
                        "status": r["status"],
                        "updated_at": r["first_seen"],
                    }
                )
            return out

    approvals = _safe_section("approvals", load_approvals, [], warnings)
    applications = _safe_section("applications", load_applications, [], warnings)
    jobs = _safe_section("jobs", load_jobs, [], warnings)
    last_run = _safe_section("last_run", read_run_status, {}, warnings)

    return {
        "jobs_tracked": len(jobs),
        "application_count": len(applications),
        "pending_approvals": len(approvals),
        "recent_jobs": len(jobs),
        "approvals": approvals,
        "applications": applications,
        "jobs": jobs,
        "last_run": last_run,
        "warnings": warnings,
    }


class _Handler(BaseHTTPRequestHandler):
    server_version = "LinkedInAgentDashboard/1.0"

    def _send(self, status, payload, content_type="application/json; charset=utf-8"):
        raw = payload if isinstance(payload, bytes) else json.dumps(payload, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, _HTML.encode(), "text/html; charset=utf-8")
        elif path == "/api/health":
            self._send(200, {"ok": True, "service": "linkedin-agent-dashboard"})
        elif path == "/api/summary":
            try:
                self._send(200, _summary())
            except Exception as exc:
                self._send(500, {"error": f"{type(exc).__name__}: {exc}"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/skill":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length) or b"{}")
                skill = str(body.get("skill", "")).strip()
                allowed = {"profile", "jobs", "people", "companies", "posts", "saved", "notifications"}
                if skill not in allowed:
                    self._send(400, {"error": "unsupported read-only skill"})
                    return
                from .skill_runtime import run_read
                query = str(body.get("query", "")).strip()
                location = str(body.get("location", "")).strip()
                data = asyncio.run(run_read(skill, keywords=query, location=location, query=query))
                payload = data.data
                if hasattr(payload, "to_dict"):
                    payload = payload.to_dict()
                elif isinstance(payload, list):
                    payload = [x.to_dict() if hasattr(x, "to_dict") else x for x in payload]
                self._send(200, {"skill": skill, "result": payload, "diagnostics": getattr(data, "diagnostics", {}) or {}})
            except Exception as exc:
                self._send(500, {"error": f"{type(exc).__name__}: {exc}"})
            return
        if path == "/api/agent":
            try:
                from .daily_agent import run_agent_once

                self._send(200, asyncio.run(run_agent_once()).to_dict())
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
        self._send(404, {"error": "not found"})

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
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
