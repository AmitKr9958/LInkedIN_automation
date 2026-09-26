from __future__ import annotations

import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .application_tracker import ApplicationTracker
from .approval_queue import ApprovalQueue
from .history import History
from .daily_agent import run_agent_once

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
.small{color:#667085;font-size:13px}
</style></head><body><header><strong>LinkedIn Agent Control Center</strong>
<div class="small" style="color:#d0d5dd">Local-only · read/draft/approval governed</div></header><main>
<div class="grid" id="stats"></div>
<div class="card"><h2>Agent</h2><button class="primary" onclick="runAgent()">Run Agent Now</button>
<button onclick="refresh()">Refresh</button><span id="status" class="small"></span><pre id="agent">No run yet.</pre></div>
<div class="card"><h2>Pending approvals</h2><div style="overflow:auto"><table><thead><tr><th>Action</th><th>Target</th><th>Created</th><th></th></tr></thead><tbody id="approvals"></tbody></table></div></div>
<div class="card"><h2>Applications</h2><div style="overflow:auto"><table><thead><tr><th>Title</th><th>Company</th><th>Status</th><th>Updated</th></tr></thead><tbody id="applications"></tbody></table></div></div>
<div class="card"><h2>Recent jobs</h2><div style="overflow:auto"><table><thead><tr><th>Title</th><th>Company</th><th>Status</th><th>Updated</th></tr></thead><tbody id="jobs"></tbody></table></div></div>
</main><script>
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function api(path,opts){const r=await fetch(path,opts);const d=await r.json();if(!r.ok)throw new Error(d.error||r.statusText);return d}
async function refresh(){const d=await api('/api/summary');
document.getElementById('stats').innerHTML=[['Jobs tracked',d.jobs_tracked],['Applications',d.applications],['Pending approvals',d.pending_approvals],['Recent jobs',d.recent_jobs]].map(x=>'<div class="card"><div class="small">'+esc(x[0])+'</div><h2>'+esc(x[1])+'</h2></div>').join('');
document.getElementById('approvals').innerHTML=d.approvals.map(x=>'<tr><td>'+esc(x.action)+'</td><td>'+esc(x.target)+'</td><td>'+esc(x.created_at)+'</td><td><button class="primary" onclick="decide(\''+x.id+'\',true)">Approve</button><button class="danger" onclick="decide(\''+x.id+'\',false)">Reject</button></td></tr>').join('')||'<tr><td colspan="4">No pending approvals</td></tr>';
document.getElementById('applications').innerHTML=d.applications.map(x=>'<tr><td>'+esc(x.title)+'</td><td>'+esc(x.company)+'</td><td>'+esc(x.status)+'</td><td>'+esc(x.updated_at)+'</td></tr>').join('')||'<tr><td colspan="4">None</td></tr>';
document.getElementById('jobs').innerHTML=d.jobs.map(x=>'<tr><td>'+esc(x.title)+'</td><td>'+esc(x.company)+'</td><td>'+esc(x.status)+'</td><td>'+esc(x.updated_at)+'</td></tr>').join('')||'<tr><td colspan="4">None</td></tr>'}
async function decide(id,approved){await api('/api/approvals/'+encodeURIComponent(id),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approved})});refresh()}
async function runAgent(){const s=document.getElementById('status');s.textContent=' Running read-only discovery…';try{const d=await api('/api/agent',{method:'POST'});document.getElementById('agent').textContent=JSON.stringify(d,null,2);s.textContent=' Completed';refresh()}catch(e){s.textContent=' Failed: '+e.message}}
refresh();
</script></body></html>"""

def _summary():
    approvals = ApprovalQueue().list_pending()
    applications = ApplicationTracker().list()[:20]
    jobs = History().recent(20)
    return {
        "jobs_tracked": len(jobs), "applications": len(applications),
        "pending_approvals": len(approvals), "recent_jobs": len(jobs),
        "approvals": [a.__dict__ for a in approvals],
        "applications": [dict(zip(["job_url","title","company","status","updated_at","notes"], r)) for r in applications],
        "jobs": [{"url":r[0],"title":r[1],"company":r[2],"status":r[3],"updated_at":r[4]} for r in jobs],
    }

class _Handler(BaseHTTPRequestHandler):
    server_version = "LinkedInAgentDashboard/1.0"
    def _send(self, status, payload, content_type="application/json; charset=utf-8"):
        raw = payload if isinstance(payload, bytes) else json.dumps(payload, default=str).encode()
        self.send_response(status); self.send_header("Content-Type",content_type); self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/": self._send(200,_HTML.encode(),"text/html; charset=utf-8")
        elif path == "/api/summary":
            try: self._send(200,_summary())
            except Exception as exc: self._send(500,{"error":str(exc)})
        else: self._send(404,{"error":"not found"})
    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/agent":
            try: self._send(200,asyncio.run(run_agent_once()).to_dict())
            except Exception as exc: self._send(500,{"error":f"{type(exc).__name__}: {exc}"})
            return
        if path.startswith("/api/approvals/"):
            item_id = path.rsplit("/",1)[-1]
            try:
                length=int(self.headers.get("Content-Length","0")); body=json.loads(self.rfile.read(length) or b"{}")
                changed=ApprovalQueue().decide(item_id,bool(body.get("approved",False)))
                self._send(200 if changed else 404,{"changed":changed})
            except Exception as exc: self._send(400,{"error":str(exc)})
            return
        self._send(404,{"error":"not found"})
    def log_message(self, fmt, *args): return

def serve(host="127.0.0.1", port=8765):
    server=ThreadingHTTPServer((host,port),_Handler)
    print(f"dashboard: http://{host}:{port}")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
