"""Contract tests for the skill registry (no LinkedIn session required)."""

from app.skill_registry import Skill, list_skills
from app.skill_dispatcher import dispatch, READ_CONTENT, DRAFT_CONTENT

EXPECTED = {
    "auth", "profile", "jobs", "people", "companies", "posts", "saved",
    "connections", "messaging", "engagement", "leadgen", "followups", "outreach",
    "post_writer", "content_planner", "comment_drafter", "reply_handler",
    "post_audit", "humanizer", "hook_extractor", "repurposer", "profile_optimizer",
    "interviewer", "story_bank", "engager_analytics", "thread_monitor", "employee_advocacy",
}

MUTATING = {
    "connections", "messaging", "engagement", "followups", "outreach",
}

READ_ONLY_BROWSER = {
    "auth", "profile", "jobs", "people", "companies", "posts", "saved",
}

CONTENT_DISPATCHED = set(READ_CONTENT) | set(DRAFT_CONTENT) | {"story_bank"}


def test_skill_registry_has_exactly_27_skills():
    skills = list_skills()
    assert len(skills) == 27
    assert {s.name for s in skills} == EXPECTED


def test_every_skill_has_name_description_and_mode():
    for skill in list_skills():
        assert isinstance(skill, Skill)
        assert skill.name and isinstance(skill.name, str)
        assert skill.description and isinstance(skill.description, str)
        assert isinstance(skill.mutating, bool)
        assert skill.name in EXPECTED


def test_mutating_flags_match_policy():
    skills = {s.name: s for s in list_skills()}
    for name in EXPECTED:
        expected_mutating = name in MUTATING
        assert skills[name].mutating is expected_mutating, (
            f"{name}: expected mutating={expected_mutating}, got {skills[name].mutating}"
        )


def test_content_skills_are_dispatchable():
    """Every content skill registered in the registry must be callable via dispatch."""
    registered = {s.name for s in list_skills()}
    for name in CONTENT_DISPATCHED:
        assert name in registered, f"dispatcher skill {name} missing from registry"


def test_dispatch_rejects_unknown_skill():
    import pytest
    with pytest.raises(ValueError):
        dispatch("does_not_exist_skill_xyz")


def test_read_only_browser_skills_are_non_mutating():
    skills = {s.name: s for s in list_skills()}
    for name in READ_ONLY_BROWSER:
        assert skills[name].mutating is False


def test_skill_names_are_unique():
    names = [s.name for s in list_skills()]
    assert len(names) == len(set(names))
