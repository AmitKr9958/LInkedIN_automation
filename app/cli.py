import asyncio
import json
import typer

from .application_tracker import ApplicationTracker, STATUSES
from .job_normalize import dedupe_jobs
from .doctor import run_doctor
from .orchestrator import build_discovery_report
from .approval_queue import ApprovalQueue
from .config import settings
from .skill_registry import list_skills
from .skill_runtime import run_read
from .workflows import login_check

app = typer.Typer(help="Local LinkedIn workflow assistant")


@app.command()
def doctor():
    """Run local production-readiness checks."""
    checks = run_doctor()
    for check in checks:
        typer.echo(f"[{"PASS" if check.ok else "FAIL"}] {check.name}: {check.detail}")
    raise typer.Exit(code=0 if all(x.ok for x in checks) else 1)


@app.command()
def status():
    result = asyncio.run(login_check())
    typer.echo(f"{result.action}: {result.status} - {result.details}")
    typer.echo(f"dry_run={settings.dry_run}, headless={settings.headless}")


@app.command()
def login():
    typer.echo("A visible browser will open. Log in manually; credentials are never requested or exported.")
    result = asyncio.run(login_check())
    typer.echo(f"{result.status}: {result.details}")


@app.command("skills")
def skills():
    for skill in list_skills():
        mode = "mutating" if skill.mutating else "read/draft"
        typer.echo(f"- {skill.name}: {skill.description} [{mode}]")


@app.command("read")
def read(skill: str, query: str = "", location: str = ""):
    """Run a read-only skill and print JSON."""
    if skill in {"jobs", "people"} and not query:
        query = "Power BI" if skill == "jobs" else "Power BI recruiter"
    if skill == "companies" and not query:
        query = "technology"
    if skill == "posts" and not query:
        query = "Power BI"
    data = asyncio.run(run_read(skill, keywords=query, location=location, query=query))
    payload = data.data
    if hasattr(payload, "to_dict"):
        payload = payload.to_dict()
    elif isinstance(payload, list):
        payload = [x.to_dict() if hasattr(x, "to_dict") else x for x in payload]
    typer.echo(json.dumps(payload, indent=2, default=str))




@app.command("discover-jobs")
def discover_jobs(query: str = "Power BI", location: str = "Gurgaon"):
    """Discover jobs, deduplicate them, rank them, and store local history."""
    async def _run():
        data = await run_read("jobs", keywords=query, location=location)
        rows = [x.to_dict() if hasattr(x, "to_dict") else x for x in data.data]
        rows = dedupe_jobs(rows)
        normalized = [
            {
                "title": r.get("title", ""),
                "company": r.get("company", ""),
                "location": r.get("location", ""),
                "url": r.get("href") or r.get("url", ""),
                "posted_text": r.get("posted", ""),
                "description": r.get("text", ""),
                "easy_apply": bool(r.get("easy_apply", False)),
                "source": "linkedin",
            }
            for r in rows
        ]
        return build_discovery_report(normalized)

    report = asyncio.run(_run())
    typer.echo(json.dumps(report.ranked, indent=2, default=str))


@app.command("approvals")
def approvals():
    """List pending human approvals."""
    for item in ApprovalQueue().list_pending():
        typer.echo(f"{item.id} | {item.action} | {item.target} | {item.created_at}")


@app.command("approve")
def approve(item_id: str):
    ApprovalQueue().decide(item_id, True)
    typer.echo(f"approved: {item_id}")


@app.command("reject")
def reject(item_id: str):
    ApprovalQueue().decide(item_id, False)
    typer.echo(f"rejected: {item_id}")


applications = typer.Typer(help="Track job applications locally.")
app.add_typer(applications, name="applications")


@applications.command("add")
def application_add(job_url: str, title: str = "", company: str = ""):
    ApplicationTracker().add(job_url, title, company)
    typer.echo(f"tracked: {job_url}")


@applications.command("transition")
def application_transition(job_url: str, new_status: str, notes: str = ""):
    if new_status not in STATUSES:
        raise typer.BadParameter(f"status must be one of: {', '.join(STATUSES)}")
    ApplicationTracker().transition(job_url, new_status, notes)
    typer.echo(f"{job_url}: {new_status}")


@applications.command("list")
def application_list(status: str = ""):
    if status and status not in STATUSES:
        raise typer.BadParameter(f"status must be one of: {', '.join(STATUSES)}")
    rows = ApplicationTracker().list(status or None)
    for row in rows:
        typer.echo(" | ".join(str(value) for value in row))
