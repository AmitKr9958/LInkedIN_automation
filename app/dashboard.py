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
            return count, [dict(r) for r in rows]

    def load_jobs():
        with _db(activity) as db:
            count = db.execute("SELECT COUNT(*) FROM job_history").fetchone()[0]
            rows = db.execute(
                "SELECT title,company,location,url,score,reasons,status,first_seen "
                "FROM job_history ORDER BY id DESC LIMIT 50"
            ).fetchall()
            out = []
            for r in rows:
                out.append(
                    {
                        "title": r["title"],
                        "company": r["company"],
                        "location": r["location"],
                        "url": r["url"],
                        "score": r["score"],
                        "reasons": r["reasons"],
                        "status": r["status"],
                        "updated_at": r["first_seen"],
                    }
                )
            return count, out

    approvals = _safe_section("approvals", load_approvals, [], warnings)
    application_data = _safe_section("applications", load_applications, (0, []), warnings)
    job_data = _safe_section("jobs", load_jobs, (0, []), warnings)
    last_run = _safe_section("last_run", read_run_status, {}, warnings)

    return {
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
 --bg:#f4f7fb;--panel:#fff;--ink:#101828;--muted:#667085;--line:#e4e7ec;
 --blue:#0a66c2;--blue2:#004182;--green:#12b76a;--amber:#f79009;--red:#f04438;
 --nav:#0b1625;--nav2:#12233a;--shadow:0 8px 28px rgba(16,24,40,.07)
}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;color:var(--ink);background:var(--bg)}
button,input,textarea,select{font:inherit}button{border:0;cursor:pointer}
.app{display:flex;min-height:100vh}.sidebar{width:240px;background:linear-gradient(180deg,var(--nav),#08111e);color:#fff;padding:20px 14px;position:fixed;inset:0 auto 0 0;z-index:5}
.brand{display:flex;gap:10px;align-items:center;padding:4px 8px 22px}.brand-mark{width:34px;height:34px;border-radius:9px;background:#0a66c2;display:grid;place-items:center;font-weight:800}
.brand strong{display:block;font-size:15px}.brand span{display:block;color:#98a2b3;font-size:11px}
.nav{display:grid;gap:4px}.nav button{background:transparent;color:#b8c4d4;text-align:left;padding:11px 12px;border-radius:8px;width:100%;font-weight:600}
.nav button:hover,.nav button.active{background:var(--nav2);color:#fff}.nav small{color:#667085;padding:18px 12px 6px;text-transform:uppercase;letter-spacing:.08em}
.main{margin-left:240px;width:calc(100% - 240px);padding:22px 28px 44px}.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px}
.title h1{font-size:25px;margin:0 0 3px}.title p{margin:0;color:var(--muted)}
.actions{display:flex;gap:8px}.btn{padding:9px 13px;border-radius:8px;background:#fff;border:1px solid var(--line);font-weight:650}.btn.primary{background:var(--blue);color:#fff;border-color:var(--blue)}.btn.primary:hover{background:var(--blue2)}.btn:disabled{opacity:.55;cursor:not-allowed}
.view{display:none}.view.active{display:block}.grid{display:grid;gap:14px}.metrics{grid-template-columns:repeat(5,minmax(0,1fr));margin-bottom:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);padding:18px}.metric{min-height:106px}.metric .label{color:var(--muted);font-size:12px;font-weight:650}.metric .value{font-size:27px;font-weight:800;margin-top:10px}.metric .hint{font-size:11px;color:var(--muted);margin-top:2px}
.two{grid-template-columns:1.5fr 1fr}.three{grid-template-columns:repeat(3,1fr)}
.cardhead{display:flex;align-items:center;justify-content:space-between;margin-bottom:13px}.card h2{font-size:16px;margin:0}.cardhead p{margin:3px 0 0;color:var(--muted);font-size:12px}
.health{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:750}.dot{width:8px;height:8px;border-radius:50%;background:var(--green);display:inline-block}.dot.amber{background:var(--amber)}.dot.red{background:var(--red)}
.hero{background:linear-gradient(135deg,#0b1f35,#0a66c2);color:#fff;padding:23px;border-radius:14px;box-shadow:var(--shadow);margin-bottom:16px}.hero h2{margin:0 0 6px;font-size:22px}.hero p{color:#d7e6f7;margin:0 0 16px;max-width:720px}.hero .btn{background:#fff;color:#0a66c2}
.quick{grid-template-columns:repeat(4,1fr)}.quick button{padding:15px;text-align:left;background:#fff;border:1px solid var(--line);border-radius:10px;box-shadow:0 2px 8px rgba(16,24,40,.03)}
.quick button:hover{border-color:#9fc5e8;transform:translateY(-1px)}.quick b{display:block}.quick span{display:block;color:var(--muted);font-size:11px;margin-top:3px}
pre{white-space:pre-wrap;word-break:break-word;max-height:420px;overflow:auto;background:#0b1220;color:#dce7f5;padding:15px;border-radius:9px;margin:0;font-size:12px}
.tablewrap{overflow:auto}.table{width:100%;border-collapse:collapse}.table th{font-size:11px;text-transform:uppercase;color:var(--muted);letter-spacing:.04em;text-align:left;padding:10px 8px;border-bottom:1px solid var(--line)}.table td{padding:11px 8px;border-bottom:1px solid #f0f2f5;vertical-align:top}.table tr:hover td{background:#fafcff}
.badge{display:inline-flex;padding:3px 8px;border-radius:999px;background:#eef4ff;color:#175cd3;font-size:11px;font-weight:700}.badge.green{background:#ecfdf3;color:#067647}.badge.amber{background:#fffaeb;color:#b54708}.badge.red{background:#fef3f2;color:#b42318}
.muted{color:var(--muted)}.error{padding:12px;background:#fef3f2;border:1px solid #fecdca;color:#b42318;border-radius:9px}.empty{padding:30px;text-align:center;color:var(--muted)}
.skills{grid-template-columns:repeat(3,1fr)}.skill{border:1px solid var(--line);border-radius:11px;padding:15px;background:#fff}.skill:hover{border-color:#98c3e6;box-shadow:var(--shadow)}.skilltop{display:flex;justify-content:space-between;gap:10px}.skill h3{font-size:14px;margin:0 0 5px}.skill p{font-size:12px;color:var(--muted);margin:0 0 12px}.skill .btn{padding:7px 10px}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}.search{flex:1;min-width:220px;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:#fff}
.drawer{position:fixed;inset:0;background:rgba(16,24,40,.45);z-index:20;display:none}.drawer.open{display:block}.drawerbox{position:absolute;right:0;top:0;height:100%;width:min(620px,95vw);background:#fff;padding:24px;overflow:auto;box-shadow:-10px 0 40px rgba(0,0,0,.18)}.drawerhead{display:flex;justify-content:space-between;align-items:flex-start}.drawer h2{margin:0}.field{margin:15px 0}.field label{display:block;font-size:12px;font-weight:700;margin-bottom:6px}.field input,.field textarea,.field select{width:100%;border:1px solid var(--line);border-radius:8px;padding:10px}.field textarea{min-height:120px;resize:vertical}.readonly{background:#f8fafc}.notice{padding:11px;border-radius:8px;background:#eff8ff;color:#175cd3;font-size:12px}.danger{color:#b42318}
.task{padding:12px;border:1px solid var(--line);border-radius:9px;background:#fff;margin-top:10px}.progress{height:7px;background:#eaecf0;border-radius:99px;overflow:hidden;margin-top:8px}.progress i{display:block;height:100%;width:35%;background:var(--blue);animation:load 1.2s infinite ease-in-out alternate}@keyframes load{to{width:85%}}
@media(max-width:1000px){.sidebar{width:70px}.brand span,.brand strong,.nav small,.nav button span{display:none}.nav button{text-align:center}.main{margin-left:70px;width:calc(100% - 70px)}.metrics{grid-template-columns:repeat(2,1fr)}.quick,.skills,.two,.three{grid-template-columns:1fr 1fr}}
@media(max-width:650px){.sidebar{display:none}.main{margin:0;width:100%;padding:15px}.metrics,.quick,.skills,.two,.three{grid-template-columns:1fr}.topbar{align-items:flex-start;gap:10px}.actions{flex-wrap:wrap}}
</style>
</head>
<body>
<div class="app">
<aside class="sidebar">
  <div class="brand"><div class="brand-mark">in</div><div><strong>LinkedIn Agent</strong><span>Control Center</span></div></div>
  <nav class="nav">
    <button class="active" data-view="overview">⌂ <span>Overview</span></button>
    <button data-view="skills">✦ <span>Skill Center</span></button>
    <button data-view="jobs">▣ <span>Jobs</span></button>
    <button data-view="applications">✓ <span>Applications</span></button>
    <button data-view="approvals">⚑ <span>Approvals</span></button>
    <button data-view="agent">◉ <span>Agent Runs</span></button>
    <button data-view="system">⚙ <span>System</span></button>
  </nav>
  <div style="position:absolute;left:14px;right:14px;bottom:18px;color:#667085;font-size:11px">Local-only<br>Human approval protected</div>
</aside>
<main class="main">
<header class="topbar">
  <div class="title"><h1 id="pageTitle">Overview</h1><p>Read, research, draft and approve — from one place.</p></div>
  <div class="actions"><span id="health" class="health"><i class="dot"></i> Checking</span><button class="btn" onclick="refreshAll()">↻ Refresh</button><button class="btn primary" onclick="startAgent()">Run Agent</button></div>
</header>

<section id="overview" class="view active">
  <div class="grid metrics" id="metrics"></div>
  <div class="hero"><h2>Your LinkedIn workspace is ready</h2><p>Use Skill Center for individual workflows or Run Agent for the complete read-only job and hiring discovery cycle. Long-running LinkedIn tasks run in the background so the UI stays responsive.</p><button class="btn" onclick="showView('skills')">Open Skill Center →</button></div>
  <div class="grid quick">
    <button onclick="openSkill('jobs')"><b>Find Power BI jobs</b><span>LinkedIn · Delhi / Gurgaon / Noida</span></button>
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

<section id="jobs" class="view"><div class="card"><div class="cardhead"><div><h2>Job Intelligence</h2><p>Stored discovery history and application signals.</p></div><button class="btn primary" onclick="openSkill('jobs')">Search LinkedIn jobs</button></div><div class="tablewrap"><table class="table" id="jobsTable"></table></div></div></section>
<section id="applications" class="view"><div class="card"><div class="cardhead"><div><h2>Application Pipeline</h2><p>Local application tracking.</p></div></div><div class="tablewrap"><table class="table" id="appsTable"></table></div></div></section>
<section id="approvals" class="view"><div class="card"><div class="cardhead"><div><h2>Approval Queue</h2><p>Nothing is sent or published automatically.</p></div></div><div class="tablewrap"><table class="table" id="approvalTable"></table></div></div></section>
<section id="agent" class="view"><div class="grid two"><div class="card"><div class="cardhead"><div><h2>Agent Runs</h2><p>Run the complete governed discovery cycle.</p></div><button class="btn primary" onclick="startAgent()">Run Agent Now</button></div><div id="tasks"></div></div><div class="card"><h2>Last run details</h2><pre id="agentDetails"></pre></div></div></section>
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
 return '<thead><tr><th>Role</th><th>Company</th><th>Location</th><th>Status</th><th>Seen</th></tr></thead><tbody>'+
 (rows||[]).map(x=>'<tr><td><b>'+esc(x.title)+'</b></td><td>'+esc(x.company)+'</td><td>'+esc(x.location)+'</td><td><span class="badge">'+esc(x.status||'new')+'</span></td><td>'+esc(x.updated_at)+'</td></tr>').join('')+
 '</tbody>' || '<tbody><tr><td colspan="5" class="empty">No jobs stored yet.</td></tr></tbody>';
}
function renderTables(d){
 document.getElementById('jobsTable').innerHTML=jobRows(d.jobs);
 document.getElementById('overviewJobs').innerHTML=jobRows((d.jobs||[]).slice(0,8));
 document.getElementById('appsTable').innerHTML='<thead><tr><th>Role</th><th>Company</th><th>Status</th><th>Updated</th></tr></thead><tbody>'+
 (d.applications||[]).map(x=>'<tr><td><b>'+esc(x.title)+'</b></td><td>'+esc(x.company)+'</td><td><span class="badge">'+esc(x.status)+'</span></td><td>'+esc(x.updated_at)+'</td></tr>').join('')+'</tbody>';
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
document.getElementById('skillSearch').oninput=renderSkills;document.getElementById('modeFilter').onchange=renderSkills;

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
   if(d.status==='completed'){el.innerHTML='<div class="task"><span class="badge green">Completed</span></div>';output.innerHTML='<pre>'+esc(JSON.stringify(d.result,null,2))+'</pre>';refreshAll()}
   else{el.innerHTML='<div class="error">Failed: '+esc(d.error)+'</div>'}
  }catch(e){el.innerHTML='<div class="error">'+esc(e.message)+'</div>'}
 };poll();
}
async function startAgent(){
 try{const d=await api('/api/agent',{method:'POST'});showView('agent');document.getElementById('tasks').innerHTML='<div class="task"><b>Agent queued</b><div class="progress"><i></i></div></div>';watchAgent(d.task_id)}
 catch(e){document.getElementById('tasks').innerHTML='<div class="error">'+esc(e.message)+'</div>'}
}
async function watchAgent(id){
 const poll=async()=>{const d=await api('/api/tasks/'+id);document.getElementById('tasks').innerHTML='<div class="task"><b>'+esc(d.status)+'</b>'+(d.status==='queued'||d.status==='running'?'<div class="progress"><i></i></div>':'')+(d.error?'<p class="danger">'+esc(d.error)+'</p>':'')+(d.status==='completed'?'<pre style="margin-top:10px">'+esc(JSON.stringify(d.result,null,2))+'</pre>':''); if(d.status==='queued'||d.status==='running')setTimeout(poll,1000);else refreshAll()};poll();
}
async function decide(id,approved){
 try{await api('/api/approvals/'+encodeURIComponent(id),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approved})});refreshAll()}catch(e){alert(e.message)}
}
function renderSystem(){document.getElementById('systemDetails').textContent=JSON.stringify({skills:state.skills.length,summary:state.summary?.warnings||[],last_run:state.summary?.last_run||{}},null,2)}
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
        self.send_header("Access-Control-Allow-Origin", "*")
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
            self._send(200, {"service":"linkedin-agent-dashboard","host":"127.0.0.1","port":self.server.server_address[1],"skills":len(skill_catalog()),"version":"2.0"})
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
