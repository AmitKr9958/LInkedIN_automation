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
