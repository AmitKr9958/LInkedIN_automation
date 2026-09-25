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
    "app.media",
    "app.publishing",
    "app.application_tracker",
    "app.history",
    "app.approval_queue",
    "app.orchestrator",
    "app.job_metadata",
    "app.resume_match",
    "app.resume_tailoring",
    "app.notifications",
    "app.scheduler",
    "app.media_provider",
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
    results.append(SelfTestResult("skill-registry", len(skills) == 27, f"{len(skills)} skills registered"))
    expected_names = {
        "auth", "profile", "jobs", "people", "companies", "posts", "saved",
        "connections", "messaging", "engagement", "leadgen", "followups", "outreach",
        "post_writer", "content_planner", "comment_drafter", "reply_handler",
        "post_audit", "humanizer", "hook_extractor", "repurposer", "profile_optimizer",
        "interviewer", "story_bank", "engager_analytics", "thread_monitor", "employee_advocacy",
    }
    missing_names = expected_names - names
    unexpected_names = names - expected_names
    expected_mutating = {"connections", "messaging", "engagement", "followups", "outreach"}
    actual_mutating = {skill.name for skill in skills if skill.mutating}
    results.append(SelfTestResult(
        "skill-contract",
        len(skills) == 27 and not missing_names and not unexpected_names and actual_mutating == expected_mutating,
        f"missing={sorted(missing_names)} unexpected={sorted(unexpected_names)} mutating={sorted(actual_mutating)}",
    ))


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
            kwargs = {}
            if name == "post_audit":
                kwargs = {"text": "A 20% result.\n\nWhat do you think?"}
            elif name in {"humanizer", "hook_extractor"}:
                kwargs = {"text": "A 20% result.\n\nWhat do you think?"}
            elif name == "post_writer":
                kwargs = {"topic": "Power BI", "angle": "a measured improvement"}
            elif name == "content_planner":
                kwargs = {"theme": "Power BI", "audience": "recruiters"}
            elif name == "comment_drafter":
                kwargs = {"post_text": "Power BI post", "point": "Useful point"}
            elif name == "reply_handler":
                kwargs = {"comment_text": "Question", "response": "Answer"}
            elif name == "repurposer":
                kwargs = {"source": "Power BI improved refresh time.", "goal": "engagement"}
            elif name == "profile_optimizer":
                kwargs = {"profile": {"headline": "BI Developer"}}
            elif name == "interviewer":
                kwargs = {"topic": "Power BI"}
            elif name == "engager_analytics":
                kwargs = {"rows": [], "target_titles": ["recruiter"]}
            elif name == "thread_monitor":
                kwargs = {"rows": []}
            elif name == "employee_advocacy":
                kwargs = {"team_size": 1, "goal": "reach"}
            elif name == "story_bank":
                kwargs = {"action": "list", "limit": 1}
            if name not in names:
                missing.append(name)
                continue
            dispatch(name, **kwargs)
        results.append(SelfTestResult("skill-dispatch", not missing, "all content skills callable" if not missing else f"missing: {missing}"))
    except Exception as exc:
        results.append(SelfTestResult("skill-dispatch", False, f"{type(exc).__name__}: {exc}"))

    return results
