import asyncio
import json
from typing import Optional

import typer

from .application_tracker import ApplicationTracker, STATUSES
from .cli_intelligence import app as intelligence_app
from .job_normalize import dedupe_jobs
from .job_preferences import DEFAULT_JOB_PREFERENCES, DEFAULT_JOB_SEARCH_QUERY
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
from .agent_test import run_agent_test
from .media import build_image_prompt, build_quote_card
from .publishing import PublishRequest, queue_publish
from .daily_agent import run_agent_once
from .run_lock import AgentAlreadyRunning, agent_lock
from .run_status import read_run_status, write_run_status
from .dashboard import serve as serve_dashboard
from .telegram_notify import notify_agent_completion

app = typer.Typer(help="Local LinkedIn workflow assistant")

@app.command("selftest")
def selftest():
    """Run deterministic module and skill-contract checks."""
    results = run_selftest()
    for result in results:
        label = "PASS" if result.ok else "FAIL"
        typer.echo(f"[{label}] {result.name}: {result.detail}")
    raise typer.Exit(code=0 if all(r.ok for r in results) else 1)


@app.command("agent-test")
def agent_test(live: bool = typer.Option(False, "--live", help="Also run authenticated, read-only LinkedIn browser checks.")):
    """Run the complete agent skill contract test, optionally followed by live read-skill checks."""
    results = run_agent_test(live=live)
    failed = 0
    for result in results:
        label = "PASS" if result.ok else "FAIL"
        if not result.ok:
            failed += 1
        typer.echo(f"[{label}] {result.mode:8} {result.skill}: {result.detail}")
    typer.echo(f"summary: {len(results) - failed} passed, {failed} failed, {len(results)} total")
    raise typer.Exit(code=1 if failed else 0)


@app.command("agent-workflow-test")
def agent_workflow_test():
    """Run a safe end-to-end workflow test without changing LinkedIn."""
    from .agent_test import run_safe_workflow_test

    results = run_safe_workflow_test()
    failed = 0
    for result in results:
        label = "PASS" if result.ok else "FAIL"
        if not result.ok:
            failed += 1
        typer.echo(f"[{label}] {result.mode:8} {result.skill}: {result.detail}")
    typer.echo(f"summary: {len(results) - failed} passed, {failed} failed, {len(results)} total")
    raise typer.Exit(code=1 if failed else 0)


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


@app.command("release-check")
def release_check():
    """Run the deterministic local release gate without touching LinkedIn."""
    from .agent_test import run_safe_workflow_test

    checks = run_doctor()
    failed = [check.name for check in checks if check.blocking and not check.ok]
    for check in checks:
        label = "PASS" if check.ok else "FAIL"
        typer.echo(f"[{label}] doctor:{check.name}: {check.detail}")

    self_results = run_selftest()
    for result in self_results:
        label = "PASS" if result.ok else "FAIL"
        typer.echo(f"[{label}] selftest:{result.name}: {result.detail}")
        if not result.ok:
            failed.append(f"selftest:{result.name}")

    workflow_results = run_safe_workflow_test()
    for result in workflow_results:
        label = "PASS" if result.ok else "FAIL"
        typer.echo(f"[{label}] workflow:{result.skill}: {result.detail}")
        if not result.ok:
            failed.append(f"workflow:{result.skill}")

    total = len(checks) + len(self_results) + len(workflow_results)
    passed = total - len(failed)
    typer.echo(f"release-summary: {passed} passed, {len(failed)} failed, {total} total")
    raise typer.Exit(code=1 if failed else 0)


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
    """Show authentication state and last agent-run health summary."""
    result = asyncio.run(login_check(wait_for_login=False, open_url=f"{settings.linkedin_base_url}/feed/"))
    typer.echo(f"{result.action}: {result.status} - {result.details}")
    typer.echo(f"dry_run={settings.dry_run}, headless={settings.headless}")
    run = read_run_status()
    typer.echo("last-run: " + json.dumps({
        "status": run.get("last_status"),
        "health_state": run.get("health_state"),
        "consecutive_failures": run.get("consecutive_failures"),
        "failure_type": run.get("failure_type"),
        "updated_at": run.get("updated_at"),
        "last_started_at": run.get("last_started_at"),
        "last_finished_at": run.get("last_finished_at"),
        "last_success_at": run.get("last_success_at"),
        "last_failure_at": run.get("last_failure_at"),
        "jobs": run.get("last_job_count"),
        "hiring_posts": run.get("last_hiring_post_count"),
        "recruiters": run.get("last_recruiter_count"),
        "drafts": run.get("last_draft_count"),
        "duration_seconds": run.get("last_duration_seconds"),
        "error": run.get("last_error"),
        "commit": run.get("commit"),
        "version": run.get("version"),
    }, indent=2, default=str))


@app.command("telegram-test")
def telegram_test():
    """Send a test Telegram notification without running LinkedIn."""
    from .telegram_notify import send_telegram_message, telegram_configuration_status

    status = telegram_configuration_status()
    typer.echo("telegram-config: " + json.dumps(status))
    if not status["configured"]:
        typer.echo(
            "telegram: failed - configuration is incomplete. "
            "Set TELEGRAM_NOTIFICATIONS_ENABLED=true, TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.",
            err=True,
        )
        raise typer.Exit(code=2)
    ok = send_telegram_message("🔔 LinkedIn Automation\nTelegram notification test: connection is working.")
    typer.echo("telegram: sent" if ok else "telegram: failed")
    if not ok:
        typer.echo(
            "Check the preceding Telegram diagnostic log for the Telegram API response.",
            err=True,
        )
    raise typer.Exit(code=0 if ok else 1)


@app.command("debug-auth")
def debug_auth():
    """Show non-secret browser/session diagnostics for troubleshooting."""
    async def _run():
        from .browser import linkedin_browser
        from .skill_runtime import ensure_authenticated

        async with linkedin_browser() as browser:
            pages = browser.pages
            page = pages[0] if pages else await browser.new_page()
            try:
                state = await ensure_authenticated(page, settle_ms=4_000, attempts=3)
                auth_ok = True
                note = None
            except Exception as exc:
                auth_ok = False
                note = f"{type(exc).__name__}: {exc}"
                from .linkedin_reader import current_session_state
                try:
                    state = await current_session_state(page)
                except Exception:
                    state = {"authenticated": False, "url": page.url, "title": ""}
            return {
                "profile_path": str(settings.profile_path),
                "headless": settings.headless,
                "page_count": len(browser.pages),
                "url": page.url,
                "title": await page.title() if not page.is_closed() else "",
                "authenticated": auth_ok,
                "state": state,
                "note": note,
            }

    typer.echo(json.dumps(asyncio.run(_run()), indent=2, default=str))


@app.command()
def login():
    """Open a visible Chromium window using the persistent local profile.

    Log in to LinkedIn yourself (password, OTP, CAPTCHA). The agent never
    requests or exports credentials. After the feed is detected as
    authenticated the profile is settled and closed so the session persists
    for subsequent headless runs.
    """
    typer.echo(
        "A visible browser will open using the local profile at:\n"
        f"  {settings.profile_path}\n"
        "Log in to LinkedIn manually in that window (password / OTP / CAPTCHA).\n"
        "Credentials are never requested or exported by this tool.\n"
        "Waiting up to 15 minutes for an authenticated feed..."
    )
    result = asyncio.run(login_check(keep_open=True, force_headed=True))
    typer.echo(f"{result.status}: {result.details}")
    if result.status == "authenticated":
        typer.echo(
            "Session saved to the persistent browser profile.\n"
            "Verify headless restore with:\n"
            "  $env:HEADLESS='true'; python -m app debug-auth\n"
            "If that still reports unauthenticated, re-run login and leave the "
            "feed fully loaded for ~15 seconds before the window closes."
        )
    else:
        typer.echo(
            "Authentication was not confirmed. Keep the browser open until the "
            "LinkedIn home feed is fully loaded, then re-run: python -m app login",
            err=True,
        )
        raise typer.Exit(code=1)


@app.command("skills")
def skills():
    for skill in list_skills():
        mode = "mutating" if skill.mutating else "read/draft"
        typer.echo(f"- {skill.name}: {skill.description} [{mode}]")


@app.command("smoke-test")
def smoke_test(read_only: bool = typer.Option(True, "--read-only/--all", help="Only run read-only live checks")):
    """Run a read-only live smoke test against the authenticated browser profile.

    Does NOT perform connection requests, messages, likes, comments, or other
    mutating actions. Reports PASS/FAIL per supported read skill.
    """
    if not read_only:
        typer.echo("Only --read-only mode is supported. Mutating actions stay approval-gated.")
        raise typer.Exit(code=2)

    checks = [
        ("auth", lambda: asyncio.run(_smoke_auth())),
        ("profile", lambda: asyncio.run(run_read("profile"))),
        ("jobs", lambda: asyncio.run(run_read("jobs", keywords="Power BI", location="Gurgaon"))),
        ("people", lambda: asyncio.run(run_read("people", query="Power BI"))),
        ("companies", lambda: asyncio.run(run_read("companies", query="Power BI"))),
        ("posts", lambda: asyncio.run(run_read("posts", query="Power BI"))),
        ("saved", lambda: asyncio.run(run_read("saved"))),
    ]
    failed = 0
    for name, fn in checks:
        try:
            result = fn()
            if name == "auth":
                ok = bool(result)
            else:
                ok = result is not None
            status = "PASS" if ok else "FAIL"
            if not ok:
                failed += 1
            typer.echo(f"{name:12} {status}")
        except Exception as exc:
            failed += 1
            typer.echo(f"{name:12} FAIL  ({type(exc).__name__}: {exc})")
    raise typer.Exit(code=1 if failed else 0)


async def _smoke_auth() -> bool:
    from .browser import linkedin_browser
    from .linkedin_reader import current_session_state

    async with linkedin_browser() as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()
        if not page.url or "linkedin.com" not in page.url:
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(2000)
        state = await current_session_state(page)
        return bool(state.get("authenticated"))


@app.command("read")
def read(
    skill: str,
    query: str = "",
    location: str = "",
    max_posted_hours: Optional[float] = typer.Option(
        None,
        help=(
            "Maximum job posting age in hours. Defaults to the configured "
            "job preference (6 hours). Pass a negative value to disable the "
            "freshness filter and return all ages."
        ),
    ),
):
    """Run a read-only skill and print JSON.

    For jobs, the centralized preference posted_within_hours (6 hours) is applied
    by default. Pass --max-posted-hours <N> to override, or a negative value
    to disable freshness filtering.
    """
    if skill in {"jobs", "people"} and not query:
        query = DEFAULT_JOB_SEARCH_QUERY if skill == "jobs" else "Power BI recruiter"
    if skill == "companies" and not query:
        query = "technology"
    if skill == "posts" and not query:
        query = "Power BI"
    # None (flag omitted) → use preference default inside run_read.
    # Negative → explicitly disable freshness filter.
    kwargs = dict(keywords=query, location=location, query=query)
    if max_posted_hours is not None:
        kwargs["max_posted_hours"] = None if max_posted_hours < 0 else max_posted_hours
    data = asyncio.run(run_read(skill, **kwargs))
    if getattr(data, "diagnostics", None):
        typer.echo("read-diagnostics: " + json.dumps(data.diagnostics, default=str), err=True)
    payload = data.data
    if hasattr(payload, "to_dict"):
        payload = payload.to_dict()
    elif isinstance(payload, list):
        payload = [x.to_dict() if hasattr(x, "to_dict") else x for x in payload]
    typer.echo(json.dumps(payload, indent=2, default=str))


@app.command("profile-optimize")
def profile_optimize(
    no_llm: bool = typer.Option(False, "--no-llm", help="Run deterministic audit only; skip the configured LLM."),
    queue_review: bool = typer.Option(False, "--queue-review", help="Queue the generated report for human review."),
    output: str = typer.Option("", "--output", help="Optional JSON output path."),
    notify_telegram: bool = typer.Option(False, "--notify-telegram", help="Send the optimization summary to the configured Telegram chat."),
):
    """Audit the authenticated profile and generate bounded optimization drafts.

    This command is read-only against LinkedIn. It never edits the profile.
    --queue-review creates a human-review record. Approved profile proposals are
    executable only through the separate, explicit profile-write safety gate.
    """
    from .profile_optimizer import generate_profile_optimization, profile_fingerprint

    async def _run():
        result = await run_read("profile")
        payload = result.data.to_dict() if hasattr(result.data, "to_dict") else dict(result.data)
        report = generate_profile_optimization(payload, use_llm=not no_llm)
        output = report.to_dict()
        output["profile_fingerprint"] = profile_fingerprint(payload)
        return output

    report = asyncio.run(_run()).to_dict()
    review_id = None
    if queue_review:
        payload = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
        if len(payload.encode("utf-8")) > 64 * 1024:
            raise typer.BadParameter("optimization report exceeds the approval payload limit")
        review_id = ApprovalQueue().add(
            "profile_optimization_review",
            str(report.get("profile", {}).get("url") or settings.profile_url),
            payload,
        )
        report["review_id"] = review_id

    if output:
        from pathlib import Path
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        typer.echo(f"report: {destination}")

    if notify_telegram:
        from .telegram_notify import notify_profile_optimization
        notify_profile_optimization(
            score=int(report.get("score", 0)),
            llm_used=bool(report.get("llm_used", False)),
            findings=len(report.get("findings", [])),
            drafts=len(report.get("drafts", {})),
            review_id=review_id,
            llm_error=str(report.get("llm_error") or ""),
        )

    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))

@app.command("profile-apply")
def profile_apply(item_id: str):
    """Apply one already-approved profile optimization proposal."""
    item = ApprovalQueue().get(item_id)
    if item is None:
        raise typer.BadParameter(f"approval item not found: {item_id}")
    if item.action != "profile_optimization_review":
        raise typer.BadParameter("approval item is not a profile optimization review")
    if item.status != "approved":
        raise typer.BadParameter(f"approval must be approved first; current status: {item.status}")
    try:
        proposal = json.loads(item.payload)
        from .profile_writer import apply_approved_profile_proposal
        result = asyncio.run(apply_approved_profile_proposal(proposal))
        ApprovalQueue().mark_applied(item_id)
        from .telegram_notify import notify_profile_optimization_apply
        notify_profile_optimization_apply(
            success=True,
            review_id=item_id,
            applied=result.get("applied", []),
            verified=result.get("verified", []),
            skipped=result.get("skipped", []),
        )
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as exc:
        ApprovalQueue().mark_apply_failed(item_id, str(exc))
        from .telegram_notify import notify_profile_optimization_apply
        notify_profile_optimization_apply(success=False, review_id=item_id, error_message=f"{type(exc).__name__}: {exc}")
        raise typer.Exit(code=1)


@app.command("dashboard")
def dashboard(host: str = "127.0.0.1", port: int = 8765):
    """Start the local control-center dashboard; binds to localhost by default."""
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise typer.BadParameter("dashboard must bind to localhost")
    serve_dashboard(host, port)


@app.command("agent")
def agent(
    locations: str = typer.Option(
        "",
        "--locations",
        help="Comma-separated locations. Defaults to Delhi,Gurgaon,Noida.",
    ),
    max_posted_hours: Optional[float] = typer.Option(
        None,
        "--max-posted-hours",
        help="Override the 6-hour job freshness window. Use a negative value to disable it.",
    ),
):
    """Run the governed end-to-end workflow: discover, rank, track, target and draft."""
    import sys
    import time as _time
    from datetime import datetime, timezone

    if not settings.agent_enabled:
        typer.echo(
            "agent: blocked by safety gate. Set LINKEDIN_AGENT_ENABLED=true "
            "only after confirming the account/session is available.",
            err=True,
        )
        raise typer.Exit(code=3)

    requested_locations = [x.strip() for x in locations.split(",") if x.strip()] if locations else None
    window = None if max_posted_hours is None else (
        None if max_posted_hours < 0 else max_posted_hours
    )
    started = _time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    typer.echo(
        f"agent: starting (headless={settings.headless}, dry_run={settings.dry_run}, "
        f"max_posted_hours={window if window is not None else 'default-6'})",
        err=True,
    )
    try:
        with agent_lock():
            report = asyncio.run(
                run_agent_once(
                    locations=requested_locations,
                    max_posted_hours=window,
                )
            )
    except AgentAlreadyRunning as exc:
        typer.echo(f"agent: FAIL ({type(exc).__name__}: {exc})", err=True)
        duration = round(_time.monotonic() - started, 2)
        write_run_status(
            success=False,
            error=str(exc),
            started_at=started_at,
            duration_seconds=duration,
        )
        notify_agent_completion(
            success=False,
            duration_seconds=duration,
            error_message=str(exc),
        )
        raise typer.Exit(code=2)
    except Exception as exc:
        duration = _time.monotonic() - started
        message = f"{type(exc).__name__}: {exc}"
        typer.echo(f"agent: FAIL ({message})", err=True)
        if "session is not verified" in str(exc).lower() or "not authenticated" in str(exc).lower():
            typer.echo(
                "Authentication failure. Run: python -m app login  (HEADLESS=false), "
                "complete LinkedIn sign-in in the visible browser, then "
                "python -m app debug-auth",
                err=True,
            )
        write_run_status(
            success=False,
            duration_seconds=round(duration, 2),
            error=message,
            started_at=started_at,
        )
        notify_agent_completion(
            success=False,
            duration_seconds=duration,
            error_message=message,
        )
        sys.stderr.flush()
        sys.stdout.flush()
        raise typer.Exit(code=1)

    duration = _time.monotonic() - started
    write_run_status(
        success=True,
        jobs_found=report.jobs_found,
        new_jobs=report.new_jobs,
        hiring_posts=len(report.hiring_posts),
        recruiter_targets=len(report.recruiter_targets),
        drafts=len(report.connection_drafts),
        duration_seconds=round(duration, 2),
        started_at=started_at,
    )
    notify_agent_completion(
        success=True,
        duration_seconds=duration,
        jobs=report.jobs_found,
        new_jobs=report.new_jobs,
        tracked_jobs=report.tracked_jobs,
        hiring_posts=len(report.hiring_posts),
        recruiter_targets=len(report.recruiter_targets),
        connection_drafts=len(report.connection_drafts),
        stale_jobs_removed=int((report.diagnostics or {}).get("stale_jobs_removed", 0) or 0),
        freshness_hours=float(window if window is not None else DEFAULT_JOB_PREFERENCES.posted_within_hours),
    )
    # Emit timing diagnostics for operator visibility (no secrets).
    timings = (report.diagnostics or {}).get("timings_seconds") or {}
    if timings:
        typer.echo(f"agent-timings: {json.dumps(timings, default=str)}", err=True)
    typer.echo(json.dumps(report.to_dict(), indent=2, default=str))
    typer.echo(
        f"agent-summary: jobs={report.jobs_found} new={report.new_jobs} "
        f"tracked={report.tracked_jobs} recruiter_targets={len(report.recruiter_targets)} "
        f"connection_drafts={len(report.connection_drafts)} "
        f"duration_s={round(duration, 1)}"
    )
    typer.echo(
        "No LinkedIn account-changing action was executed. "
        "Connection/message/publish actions remain approval-gated."
    )


@app.command("discover-jobs")
def discover_jobs(query: str = DEFAULT_JOB_SEARCH_QUERY, location: str = "Gurgaon"):
    """Discover jobs, deduplicate them, rank them, and store local history."""
    async def _run():
        data = await run_read("jobs", keywords=query, location=location)
        if getattr(data, "diagnostics", None):
            typer.echo("read-diagnostics: " + json.dumps(data.diagnostics, default=str), err=True)
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
