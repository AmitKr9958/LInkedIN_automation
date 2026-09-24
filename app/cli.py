import asyncio
import json

import typer

from .application_tracker import ApplicationTracker, STATUSES
from .cli_intelligence import app as intelligence_app
from .job_normalize import dedupe_jobs
from .history import History
from .doctor import run_doctor
from .orchestrator import build_discovery_report
from .approval_queue import ApprovalQueue
from .config import settings
from .reporting import application_rows, export_rows
from .skill_registry import list_skills
from .skill_runtime import run_read
from .workflows import login_check
from .post_audit import audit_post
from .story_bank import Story, StoryBank
from .outreach import OutreachTarget, draft_connection, draft_followup
from .agent import LinkedInAgent
from .selftest import run_selftest
from .media import build_image_prompt, build_quote_card
from .publishing import PublishRequest, queue_publish

app = typer.Typer(help="Local LinkedIn workflow assistant")

@app.command("selftest")
def selftest():
    """Run deterministic module and skill-contract checks."""
    results = run_selftest()
    for result in results:
        label = "PASS" if result.ok else "FAIL"
        typer.echo(f"[{label}] {result.name}: {result.detail}")
    raise typer.Exit(code=0 if all(r.ok for r in results) else 1)


@app.command("audit-post")
def audit_post_command(path: str = "", text: str = ""):
    """Audit a post draft without publishing it."""
    if path:
        text = open(path, encoding="utf-8").read()
    if not text:
        raise typer.BadParameter("provide text or a file path")
    typer.echo(json.dumps(audit_post(text), indent=2, default=str))


@app.command("story-bank")
def story_bank(action: str = "list", query: str = "", limit: int = 20):
    """List/search the local Story Bank."""
    bank = StoryBank()
    if action == "search":
        rows = bank.search(query, limit)
    elif action == "list":
        rows = bank.list(limit)
    else:
        raise typer.BadParameter("action must be list or search")
    typer.echo(json.dumps([row.to_dict() for row in rows], indent=2, default=str))


@app.command("add-story")
def add_story(title: str, situation: str = "", action: str = "", result: str = "", metric: str = "", lesson: str = "", tags: str = ""):
    """Add one reusable career story to the local Story Bank."""
    created = StoryBank().add(Story(title, situation, action, result, metric, lesson, tags))
    typer.echo(json.dumps(created.to_dict(), indent=2, default=str))


@app.command("request-connection")
def request_connection(name: str, profile_url: str, title: str = "", company: str = "", note: str = "", job_url: str = ""):
    """Queue one connection request for explicit human approval; does not auto-send."""
    target = OutreachTarget(name=name, profile_url=profile_url, title=title, company=company, target_type="manual", job_url=job_url)
    draft = {"target": target.to_dict(), "note": note, "status": "drafted"} if note else draft_connection(target, title, [])
    item = LinkedInAgent().request_action("connection_request", profile_url, draft)
    typer.echo(f"queued approval: {item}")


@app.command("request-followup")
def request_followup(name: str, profile_url: str, message: str, due_at: str = "", job_url: str = ""):
    """Queue one follow-up message for explicit human approval; does not auto-send."""
    target = OutreachTarget(name=name, profile_url=profile_url, job_url=job_url)
    draft = draft_followup(target, message, due_at or None)
    item = LinkedInAgent().request_action("followup_message", profile_url, draft)
    typer.echo(f"queued approval: {item}")



@app.command("media-prompt")
def media_prompt(text: str, kind: str = "wide", brand: str = ""):
    """Create an optional image/quote-card prompt without calling an external provider."""
    result = build_image_prompt(text, kind, brand) if kind != "quote-card" else build_quote_card(text)
    typer.echo(json.dumps(result.to_dict(), indent=2))


@app.command("request-publish")
def request_publish(text: str, scheduled_for: str = ""):
    """Queue a publishing intent for explicit human approval; does not publish directly."""
    item = queue_publish(PublishRequest(text=text, scheduled_for=scheduled_for))
    typer.echo(f"queued approval: {item}")


@app.command()
def doctor():
    """Run local production-readiness checks."""
    checks = run_doctor()
    for check in checks:
        label = "PASS" if check.ok else "FAIL"
        typer.echo(f"[{label}] {check.name}: {check.detail}")
    raise typer.Exit(code=0 if all(x.ok for x in checks if x.blocking) else 1)


@app.command()
def status():
    result = asyncio.run(login_check(wait_for_login=False, open_url=f"{settings.linkedin_base_url}/feed/"))
    typer.echo(f"{result.action}: {result.status} - {result.details}")
    typer.echo(f"dry_run={settings.dry_run}, headless={settings.headless}")


@app.command("debug-auth")
def debug_auth():
    """Show non-secret browser/session diagnostics for troubleshooting."""
    async def _run():
        from .browser import linkedin_browser
        from .linkedin_reader import current_session_state

        async with linkedin_browser() as browser:
            pages = browser.pages
            page = pages[0] if pages else await browser.new_page()
            await page.goto(settings.linkedin_base_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            state = await current_session_state(page)
            return {
                "profile_path": str(settings.profile_path),
                "page_count": len(browser.pages),
                "url": page.url,
                "title": await page.title(),
                "state": state,
            }

    typer.echo(json.dumps(asyncio.run(_run()), indent=2, default=str))


@app.command()
def login():
    typer.echo("A visible browser will open. Log in manually; credentials are never requested or exported.")
    result = asyncio.run(login_check(keep_open=True))
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
                "posted_hours": r.get("posted_hours"),
                "description": r.get("text", ""),
                "easy_apply": bool(r.get("easy_apply", False)),
                "source": "linkedin",
            }
            for r in rows
        ]
        return build_discovery_report(normalized)

    report = asyncio.run(_run())
    typer.echo(json.dumps(report.ranked, indent=2, default=str))


@app.command("history")
def history(limit: int = 20):
    """Show recently stored job history from local discovery runs."""
    rows = History().recent(limit)
    if not rows:
        typer.echo("no job history yet")
        return
    for row in rows:
        typer.echo(" | ".join(str(value) for value in row))


@app.command("export-applications")
def export_applications(
    path: str = "data/applications.json",
    fmt: str = "json",
    status: str = "",
):
    """Export locally tracked applications as JSON or CSV."""
    if fmt not in {"json", "csv"}:
        raise typer.BadParameter("fmt must be json or csv")
    if status and status not in STATUSES:
        raise typer.BadParameter(f"status must be one of: {', '.join(STATUSES)}")
    rows = ApplicationTracker().list(status or None)
    destination = export_rows(application_rows(rows), path, fmt)
    typer.echo(str(destination))


@app.command("approvals")
def approvals():
    """List pending human approvals."""
    for item in ApprovalQueue().list_pending():
        typer.echo(f"{item.id} | {item.action} | {item.target} | {item.created_at}")


@app.command("approve")
def approve(item_id: str):
    if not ApprovalQueue().decide(item_id, True):
        raise typer.BadParameter(f"approval item is missing or already decided: {item_id}")
    typer.echo(f"approved: {item_id}")


@app.command("reject")
def reject(item_id: str):
    if not ApprovalQueue().decide(item_id, False):
        raise typer.BadParameter(f"approval item is missing or already decided: {item_id}")
    typer.echo(f"rejected: {item_id}")


applications = typer.Typer(help="Track job applications locally.")
app.add_typer(applications, name="applications")
app.add_typer(intelligence_app, name="intel")


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


if __name__ == "__main__":
    app()
