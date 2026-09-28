from __future__ import annotations

import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .application_tracker import ApplicationTracker
from .approval_queue import ApprovalQueue
from .history import History
from .daily_agent import run_agent_once
from .skill_center import run_skill, skill_catalog

_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LinkedIn Skill Center</title>
<style>
body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#f5f7fb;color:#17202a}
header{background:#17202a;color:#fff;padding:18px 24px}main{max-width:1280px;margin:22px auto;padding:0 16px}
.card{background:#fff;border:1px solid #dfe3e8;border-radius:12px;padding:16px;margin-bottom:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}
.skill{cursor:pointer;text-align:left;background:#fff;border:1px solid #dfe3e8;border-radius:10px;padding:14px}
.skill:hover,.skill.active{border-color:#0a66c2;box-shadow:0 2px 8px #0001}.skill h3{margin:0 0 6px;font-size:16px}
.badge{font-size:11px;padding:3px 7px;border-radius:20px;background:#eef2f6;color:#475467}.badge.approval{background:#fff4e5;color:#9a6700}
label{display:block;font-weight:600;font-size:13px;margin:10px 0 5px}
input,textarea,select{box-sizing:border-box;width:100%;padding:9px;border:1px solid #cfd5dd;border-radius:7px;font:inherit}
textarea{min-height:100px;resize:vertical}.actions{margin-top:14px}button{border:0;border-radius:7px;padding:9px 13px;cursor:pointer;margin-right:6px}.primary{background:#0a66c2;color:#fff}
.danger{background:#b42318;color:#fff}pre{white-space:pre-wrap;max-height:480px;overflow:auto;background:#101828;color:#e6edf3;padding:14px;border-radius:8px}
.small{color:#667085;font-size:13px}.muted{color:#667085}.hidden{display:none}
table{width:100%;border-collapse:collapse}td,th{padding:9px;border-bottom:1px solid #eee;text-align:left}
.notice{padding:10px;border-radius:8px;background:#eef6ff;margin-bottom:12px}
</style></head><body>
<header><strong>LinkedIn Skill Center</strong><div class="small" style="color:#d0d5dd">Local-only · 28 skills · read / local draft / approval governed</div></header>
<main>
<div class="card"><h2>Choose a skill</h2><div class="small">Select any skill below. You do not need VS Code to use this page.</div><div id="skills" class="grid" style="margin-top:12px"></div></div>
<div id="runner" class="card hidden"><h2 id="skillTitle"></h2><div id="skillDesc" class="small"></div><div id="notice" class="notice"></div><form id="skillForm"></form>
<div class="actions"><button class="primary" onclick="runSelected(event)">Run skill</button><button type="button" onclick="clearResult()">Clear</button></div>
<h3>Result</h3><pre id="result">Select a skill and run it.</pre></div>
<div class="card"><h2>Agent & approvals</h2><button class="primary" onclick="runAgent()">Run read-only agent</button><button onclick="refresh()">Refresh</button><span id="agentStatus" class="small"></span>
<pre id="agent">No agent run from this dashboard yet.</pre>
<h3>Pending approvals</h3><div style="overflow:auto"><table><thead><tr><th>Action</th><th>Target</th><th>Created</th><th></th></tr></thead><tbody id="approvals"></tbody></table></div></div>
<div class="card"><h2>Recent jobs / applications</h2><div class="grid"><div><b>Applications</b><div id="applications" class="small"></div></div><div><b>Recent jobs</b><div id="jobs" class="small"></div></div></div></div>
</main>
<script>
let catalog=[],selected=null;
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function api(path,opts){const r=await fetch(path,opts);const d=await r.json();if(!r.ok)throw new Error(d.error||r.statusText);return d}
function renderSkills(){
 document.getElementById('skills').innerHTML=catalog.map(s=>'<button class="skill '+(selected?.name===s.name?'active':'')+'" onclick="selectSkill(\''+s.name+'\')"><h3>'+esc(s.name.replaceAll('_',' '))+'</h3><div class="small">'+esc(s.description)+'</div><br><span class="badge '+(s.mode==='approval'?'approval':'')+'">'+esc(s.mode)+'</span></button>').join('');
}
function selectSkill(name){
 selected=catalog.find(s=>s.name===name); renderSkills();
 document.getElementById('runner').classList.remove('hidden');
 document.getElementById('skillTitle').textContent=selected.name.replaceAll('_',' ');
 document.getElementById('skillDesc').textContent=selected.description;
 document.getElementById('notice').textContent=selected.mode==='approval'?'This skill prepares an approval item. It will NOT perform an account-changing LinkedIn action.':selected.mode==='read'?'This skill reads LinkedIn using the existing local browser session.':'This skill runs locally and does not need LinkedIn.';
 document.getElementById('skillForm').innerHTML=selected.fields.map(f=>'<label>'+esc(f.label)+(f.name==='topic'||f.name==='angle'?'':'')+'<\/'+ 'label>'+((f.type||'text')==='textarea'?'<textarea name="'+esc(f.name)+'">'+esc(f.default||'')+'</textarea>':'<input type="'+(f.type||'text')+'" name="'+esc(f.name)+'" value="'+esc(f.default||'')+'">')).join('');
 document.getElementById('result').textContent='Ready.';
}
async function runSelected(e){
 e.preventDefault(); if(!selected)return;
 const fd=new FormData(document.getElementById('skillForm')); const inputs=Object.fromEntries(fd.entries());
 document.getElementById('result').textContent='Running…';
 try{const d=await api('/api/skills/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({skill:selected.name,inputs})});document.getElementById('result').textContent=JSON.stringify(d,null,2);refresh()}
 catch(e){document.getElementById('result').textContent='ERROR: '+e.message}
}
function clearResult(){document.getElementById('result').textContent='Ready.'}
async function runAgent(){const s=document.getElementById('agentStatus');s.textContent=' Running…';try{const d=await api('/api/agent',{method:'POST'});document.getElementById('agent').textContent=JSON.stringify(d,null,2);s.textContent=' Completed';refresh()}catch(e){s.textContent=' Failed: '+e.message}}
async function decide(id,approved){await api('/api/approvals/'+encodeURIComponent(id),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approved})});refresh()}
async function refresh(){
 const d=await api('/api/summary');
 document.getElementById('approvals').innerHTML=d.approvals.map(x=>'<tr><td>'+esc(x.action)+'</td><td>'+esc(x.target)+'</td><td>'+esc(x.created_at)+'</td><td><button class="primary" onclick="decide(\''+x.id+'\',true)">Approve</button><button class="danger" onclick="decide(\''+x.id+'\',false)">Reject</button></td></tr>').join('')||'<tr><td colspan="4">No pending approvals</td></tr>';
 document.getElementById('applications').innerHTML=d.applications.map(x=>'<p>'+esc(x.title)+' — '+esc(x.company)+' — '+esc(x.status)+'</p>').join('')||'<p>None</p>';
 document.getElementById('jobs').innerHTML=d.jobs.map(x=>'<p>'+esc(x.title)+' — '+esc(x.company)+' — '+esc(x.status)+'</p>').join('')||'<p>None</p>';
}
async function init(){catalog=await api('/api/skills');renderSkills();refresh()}
init();
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
    server_version = "LinkedInSkillCenter/1.0"
    def _send(self, status, payload, content_type="application/json; charset=utf-8"):
        raw = payload if isinstance(payload, bytes) else json.dumps(payload, default=str).encode()
        self.send_response(status); self.send_header("Content-Type",content_type); self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def _json_body(self):
        length=int(self.headers.get("Content-Length","0"))
        return json.loads(self.rfile.read(length) or b"{}")
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/": self._send(200,_HTML.encode(),"text/html; charset=utf-8")
        elif path=="/api/summary":
            try:self._send(200,_summary())
            except Exception as exc:self._send(500,{"error":str(exc)})
        elif path=="/api/skills": self._send(200,skill_catalog())
        else:self._send(404,{"error":"not found"})
    def do_POST(self):
        path=urlparse(self.path).path
        try:
            if path=="/api/agent":
                self._send(200,asyncio.run(run_agent_once()).to_dict()); return
            if path=="/api/skills/run":
                body=self._json_body(); name=str(body.get("skill","")); inputs=body.get("inputs") or {}
                self._send(200,asyncio.run(run_skill(name,inputs))); return
            if path.startswith("/api/approvals/"):
                item_id=path.rsplit("/",1)[-1]; body=self._json_body()
                changed=ApprovalQueue().decide(item_id,bool(body.get("approved",False)))
                self._send(200 if changed else 404,{"changed":changed}); return
        except Exception as exc:
            self._send(400,{"error":f"{type(exc).__name__}: {exc}"}); return
        self._send(404,{"error":"not found"})
    def log_message(self, fmt, *args): return

def serve(host="127.0.0.1", port=8765):
    server=ThreadingHTTPServer((host,port),_Handler)
    print(f"skill-center: http://{host}:{port}")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
