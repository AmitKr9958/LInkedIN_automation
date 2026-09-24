import asyncio
import json
import typer

from .config import settings
from .skill_registry import list_skills
from .workflows import login_check
from .skill_runtime import run_read
from .approval_queue import ApprovalQueue

app = typer.Typer(help="Local LinkedIn workflow assistant")

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
    """Run a read-only skill and print JSON. Requires an existing LinkedIn browser session."""
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


if __name__ == "__main__":
    app()
