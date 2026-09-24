from app.skill_registry import list_skills

def test_all_skill_modules_are_registered():
    expected = {"auth","profile","jobs","people","companies","posts","saved","connections","messaging","engagement","leadgen","followups"}
    assert {s.name for s in list_skills()} == expected

def test_mutating_skills_are_not_auto_executed():
    skills = {s.name:s for s in list_skills()}
    for name in ("connections","messaging","engagement","followups"):
        assert skills[name].mutating is True
