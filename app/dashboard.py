from __future__ import annotations

import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .application_tracker import ApplicationTracker
from .approval_queue import ApprovalQueue
from .history import History
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
.small{color:#667085;font-size:13px}.err{color:#b42318}
</style></head><body><header><strong>LinkedIn Agent Control Center</strong>
<div class="small" style="color:#d0d5dd">Local-only · read/draft/approval governed · http://127.0.0.1:8765</div></header><main>
<div id="booterr" class="card err" style="display:none"></div>
<div class="grid" id="stats"></div>
<div class="card"><h2>Last agent run</h2><pre id="lastrun">Loading…</pre></div>
<div class="card"><h2>Agent</h2>
<p class="small">Prefer CLI for production cycles. Dashboard run is local/best-effort.</p>
<button class="primary" onclick="runAgent()">Run Agent Now</button>
<button onclick="refresh()">Refresh</button><span id="status" class="small"></span><pre id="agent">No run yet.</pre></div>
<div class="card"><h2>Pending approvals</h2><div style="overflow:auto"><table><thead><tr><th>Action</th><th>Target</th><th>Created</th><th></th></tr></thead><tbody id="approvals"></tbody></table></div></div>
<div class="card"><h2>Applications</h2><div style="overflow:auto"><table><thead><tr><th>Title</th><th>Company</th><th>Status</th><th>Updated</th></tr></thead><tbody id="applications"></tbody></table></div></div>
<div class="card"><h2>Recent jobs</h2><div style="overflow:auto"><table><thead><tr><th>Title</th><th>Company</th><th>Status</th><th>Updated</th></tr></thead><tbody id="jobs"></tbody></table></div></div>
</main><script>
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function api(path,opts){
  let r;
  try{ r=await fetch(path,opts); }
  catch(e){
    throw new Error('Cannot reach dashboard API ('+path+'). Is the server running? Start with: python -m app dashboard');
  }
  const text=await r.text();
  let d={};
  try{ d=text?JSON.parse(text):{}; }catch(_){ d={error:text||r.statusText}; }
  if(!r.ok) throw new Error(d.error||r.statusText||('HTTP '+r.status));
  return d;
}
async function refresh(){
  const boot=document.getElementById('booterr');
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
    document.getElementById('approvals').innerHTML=(d.approvals||[]).map(x=>'<tr><td>'+esc(x.action)+'</td><td>'+esc(x.target)+'</td><td>'+esc(x.created_at)+'</td><td><button class="primary" onclick="decide(\''+x.id+'\',true)">Approve</button><button class="danger" onclick="decide(\''+x.id+'\',false)">Reject</button></td></tr>').join('')||'<tr><td colspan="4">No pending approvals</td></tr>';
    document.getElementById('applications').innerHTML=(d.applications||[]).map(x=>'<tr><td>'+esc(x.title)+'</td><td>'+esc(x.company)+'</td><td>'+esc(x.status)+'</td><td>'+esc(x.updated_at)+'</td></tr>').join('')||'<tr><td colspan="4">None</td></tr>';
    document.getElementById('jobs').innerHTML=(d.jobs||[]).map(x=>'<tr><td>'+esc(x.title)+'</td><td>'+esc(x.company)+'</td><td>'+esc(x.status)+'</td><td>'+esc(x.updated_at)+'</td></tr>').join('')||'<tr><td colspan="4">None</td></tr>';
  }catch(e){
    boot.style.display='block';
    boot.textContent='Dashboard error: '+e.message;
  }
}
async function decide(id,approved){
  await api('/api/approvals/'+encodeURIComponent(id),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approved})});
  refresh();
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


def _summary() -> dict:
    approvals = ApprovalQueue().list_pending()
    application_rows = ApplicationTracker().list()[:20]
    # History.recent columns: title, company, location, url, score, reasons, status, first_seen
    job_rows = History().recent(20)
    last_run = read_run_status()
    return {
        "jobs_tracked": len(job_rows),
        "application_count": len(application_rows),
        "pending_approvals": len(approvals),
        "recent_jobs": len(job_rows),
        "approvals": [a.__dict__ for a in approvals],
        "applications": [
            dict(
                zip(
                    ["job_url", "title", "company", "status", "updated_at", "notes"],
                    r,
                )
            )
            for r in application_rows
        ],
        "jobs": [
            {
                "title": r[0],
                "company": r[1],
                "location": r[2],
                "url": r[3],
                "status": r[6],
                "updated_at": r[7],
            }
            for r in job_rows
        ],
        "last_run": last_run,
    }


class _Handler(BaseHTTPRequestHandler):
    server_version = "LinkedInAgentDashboard/1.0"

    def _send(self, status, payload, content_type="application/json; charset=utf-8"):
        raw = payload if isinstance(payload, bytes) else json.dumps(payload, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
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
