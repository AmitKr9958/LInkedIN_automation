from __future__ import annotations

import importlib
from dataclasses import dataclass

from .skill_registry import list_skills


@dataclass(frozen=True)
class SelfTestResult:
    name: str
    ok: bool
    detail: str


MODULES = (
    "app.browser",
    "app.linkedin_reader",
    "app.skill_runtime",
    "app.skill_registry",
    "app.skill_dispatcher",
    "app.content_skills",
    "app.post_audit",
    "app.voice",
    "app.story_bank",
    "app.outreach",
    "app.application_tracker",
    "app.history",
    "app.approval_queue",
    "app.orchestrator",
)


def run_selftest() -> list[SelfTestResult]:
    results: list[SelfTestResult] = []
    for module in MODULES:
        try:
            importlib.import_module(module)
            results.append(SelfTestResult(f"module:{module}", True, "import ok"))
        except Exception as exc:
            results.append(SelfTestResult(f"module:{module}", False, f"{type(exc).__name__}: {exc}"))

    skills = list_skills()
    names = {skill.name for skill in skills}
    results.append(SelfTestResult("skill-registry", len(skills) >= 26, f"{len(skills)} skills registered"))

    expected_dispatch = {
        "post_writer", "content_planner", "comment_drafter", "reply_handler",
        "humanizer", "hook_extractor", "repurposer", "profile_optimizer",
        "interviewer", "engager_analytics", "thread_monitor", "employee_advocacy",
        "post_audit", "story_bank",
    }
    try:
        from .skill_dispatcher import dispatch
        missing = []
        for name in expected_dispatch:
            kwargs = {"text": "A 20% result.\n\nWhat do you think?"} if name in {"post_audit", "humanizer", "hook_extractor"} else {}
            if name == "story_bank":
                kwargs = {"action": "list", "limit": 1}
            if name not in names:
                missing.append(name)
                continue
            dispatch(name, **kwargs)
        results.append(SelfTestResult("skill-dispatch", not missing, "all content skills callable" if not missing else f"missing: {missing}"))
    except Exception as exc:
        results.append(SelfTestResult("skill-dispatch", False, f"{type(exc).__name__}: {exc}"))

    return results
