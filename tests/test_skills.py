from app.skill_registry import list_skills

def test_skill_registry_has_twelve_skills():
    skills = list_skills()
    assert len(skills) == 12
    assert {s.name for s in skills} == {
        "auth", "profile", "jobs", "people", "companies", "posts",
        "saved", "connections", "messaging", "engagement", "leadgen", "followups"
    }
