from __future__ import annotations
import json
import typer
from .drafting import recruiter_message, followup_message
from .intelligence import JobRecord, rank_jobs
from .job_preferences import DEFAULT_JOB_PREFERENCES

app=typer.Typer(help="Offline LinkedIn intelligence tools")

@app.command("rank")
def rank(path: str):
    """Rank a JSON array of manually exported/entered job records."""
    with open(path,encoding="utf-8") as f:
        rows=json.load(f)
    jobs=[JobRecord(**row) for row in rows]
    print(json.dumps(rank_jobs(jobs,DEFAULT_JOB_PREFERENCES),indent=2))

@app.command("recruiter-draft")
def recruiter(name: str, role: str, skills: str):
    d=recruiter_message(name,role,[x.strip() for x in skills.split(",") if x.strip()])
    print(d.text)

@app.command("followup-draft")
def followup(name: str, role: str):
    print(followup_message(name,role).text)
