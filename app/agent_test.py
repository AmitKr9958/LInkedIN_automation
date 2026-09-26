from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable

from .selftest import run_selftest
from .skill_registry import list_skills
from .skill_dispatcher import dispatch
from .browser import linkedin_browser
from .linkedin_reader import current_session_state
from .skill_runtime import run_read


@dataclass(frozen=True)
class AgentTestResult:
    skill: str
    mode: str
    ok: bool
    detail: str


_CONTENT_CASES = {
    "post_writer": {"topic": "Power BI", "angle": "a measured improvement"},
    "content_planner": {"theme": "Power BI", "audience": "recruiters"},
    "comment_drafter": {"post_text": "Power BI post", "point": "Useful point"},
    "reply_handler": {"comment_text": "Question", "response": "Answer"},
    "post_audit": {"text": "I improved refresh time by 20%. What worked for you?"},
    "humanizer": {"text": "I improved refresh time by 20%. What worked for you?"},
    "hook_extractor": {"text": "I improved refresh time by 20%. What worked for you?"},
    "repurposer": {"source": "Power BI improved refresh time.", "goal": "engagement"},
    "profile_optimizer": {"profile": {"headline": "BI Developer"}},
    "interviewer": {"topic": "Power BI"},
    "engager_analytics": {"rows": [], "target_titles": ["recruiter"]},
    "thread_monitor": {"rows": []},
    "employee_advocacy": {"team_size": 1, "goal": "reach"},
    "story_bank": {"action": "list", "limit": 1},
}


async def _live_auth() -> bool:
    async with linkedin_browser() as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()
        if not page.url or "linkedin.com" not in page.url or "/feed/" not in page.url:
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(2000)
        state = await current_session_state(page)
        return bool(state.get("authenticated"))


async def _live_read(skill: str):
    kwargs = {
        "profile": {},
        "jobs": {"keywords": "Power BI", "location": "Delhi"},
        "people": {"query": "Power BI recruiter"},
        "companies": {"query": "data analytics"},
        "posts": {"query": "Power BI"},
        "saved": {},
    }[skill]
    return await run_read(skill, **kwargs)


def run_agent_contract_test() -> list[AgentTestResult]:
    results: list[AgentTestResult] = []
    for result in run_selftest():
        results.append(AgentTestResult(result.name, "contract", result.ok, result.detail))

    registered = {skill.name for skill in list_skills()}
    for name, kwargs in _CONTENT_CASES.items():
        if name not in registered:
            results.append(AgentTestResult(name, "content", False, "not registered"))
            continue
        try:
            dispatch(name, **kwargs)
            results.append(AgentTestResult(name, "content", True, "dispatch ok"))
        except Exception as exc:
            results.append(AgentTestResult(name, "content", False, f"{type(exc).__name__}: {exc}"))
    return results


async def run_live_read_test() -> list[AgentTestResult]:
    results: list[AgentTestResult] = []
    try:
        authenticated = await _live_auth()
        results.append(AgentTestResult("auth", "live", authenticated, "authenticated" if authenticated else "session not authenticated"))
    except Exception as exc:
        results.append(AgentTestResult("auth", "live", False, f"{type(exc).__name__}: {exc}"))
        return results

    for skill in ("profile", "jobs", "people", "companies", "posts", "saved"):
        try:
            data = await _live_read(skill)
            count = len(data.data) if isinstance(data.data, list) else 1
            results.append(AgentTestResult(skill, "live", True, f"read ok ({count} record(s))"))
        except Exception as exc:
            results.append(AgentTestResult(skill, "live", False, f"{type(exc).__name__}: {exc}"))
    return results


def run_agent_test(live: bool = False) -> list[AgentTestResult]:
    results = run_agent_contract_test()
    if live:
        results.extend(asyncio.run(run_live_read_test()))
    return results


def run_safe_workflow_test() -> list[AgentTestResult]:
    """Exercise job, recruiter, application and content workflows without LinkedIn mutations."""
    from tempfile import TemporaryDirectory
    from pathlib import Path
    import gc
    import json
    from types import SimpleNamespace

    from .application_tracker import ApplicationTracker
    from .approval_queue import ApprovalQueue
    from .content_skills import content_plan, write_post
    from .intelligence import JobRecord, rank_jobs
    from .job_preferences import DEFAULT_JOB_PREFERENCES
    from .outreach import build_outreach_plan, draft_connection, draft_followup

    results: list[AgentTestResult] = []
    with TemporaryDirectory() as tmp:
        job = JobRecord(
            title="Senior Power BI Developer",
            company="Example Analytics",
            location="Delhi, India (On-site)",
            url="https://www.linkedin.com/jobs/view/test",
            posted_text="30 minutes ago",
            easy_apply=True,
            source="test",
            posted_hours=0.5,
        )
        ranked = rank_jobs([job], DEFAULT_JOB_PREFERENCES)
        results.append(AgentTestResult("job-ranking", "workflow", bool(ranked and ranked[0]["score"] > 0), "ranked test job"))

        person = SimpleNamespace(
            name="Test Recruiter",
            headline="Technical Recruiter - Example Analytics",
            href="https://www.linkedin.com/in/example-recruiter",
            text="Power BI hiring",
        )
        targets = build_outreach_plan([person], job.to_dict())
        results.append(AgentTestResult("recruiter-plan", "workflow", len(targets) == 1, f"{len(targets)} target(s)"))

        connection = draft_connection(targets[0], "Senior Power BI Developer", ["Power BI", "SQL"])
        followup = draft_followup(targets[0], "Thanks for connecting about the Power BI opportunity.")
        results.append(AgentTestResult("outreach-drafts", "workflow", connection["status"] == "drafted" and followup["status"] == "drafted", "drafts created"))

        queue = ApprovalQueue(str(Path(tmp) / "approvals.sqlite3"))
        connection_id = queue.add("connection_request", targets[0].profile_url, json.dumps(connection))
        followup_id = queue.add("followup_message", targets[0].profile_url, json.dumps(followup))
        pending = queue.list_pending()
        results.append(AgentTestResult("approval-queue", "workflow", len(pending) == 2 and {x.id for x in pending} == {connection_id, followup_id}, "two actions queued"))

        tracker = ApplicationTracker(Path(tmp) / "applications.sqlite3")
        tracker.add(job.url, job.title, job.company)
        tracker.transition(job.url, "shortlisted")
        tracker.transition(job.url, "drafted")
        tracked = tracker.list()
        results.append(AgentTestResult("application-tracker", "workflow", bool(tracked and tracked[0][3] == "drafted"), "tracked through drafted"))

        draft = write_post("Power BI automation", "Share a measured 30% reduction in manual workload.")
        plan = content_plan("Power BI", "recruiters", days=3)
        results.append(AgentTestResult("content-workflow", "workflow", bool(draft.text and len(plan) == 3), "post draft and plan created"))

        # Windows can retain sqlite file handles briefly after connection
        # cleanup. Release all test objects and collect before TemporaryDirectory
        # attempts to remove the database files.
        del tracker, queue, pending, tracked
        gc.collect()

    return results
