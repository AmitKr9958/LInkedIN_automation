from app.skill_registry import list_skills


EXPECTED = {
    "auth", "profile", "jobs", "people", "companies", "posts", "saved",
    "connections", "messaging", "engagement", "leadgen", "followups",
    "post_writer", "content_planner", "comment_drafter", "reply_handler",
    "humanizer", "hook_extractor", "repurposer", "profile_optimizer",
    "interviewer", "engager_analytics", "thread_monitor", "employee_advocacy",
}


def test_skill_registry_has_expanded_skill_set():
    skills = list_skills()
    assert len(skills) == len(EXPECTED)
    assert {s.name for s in skills} == EXPECTED
