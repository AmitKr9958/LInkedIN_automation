from app.content_skills import (
    analyze_engagers, content_plan, extract_hook, humanize, profile_audit,
    thread_followups, employee_advocacy_plan,
)

def test_content_plan_bounded():
    assert len(content_plan("Power BI", "recruiters", 40)) == 31

def test_extract_hook():
    result = extract_hook("3 lessons I learned\nMore")
    assert "number" in result["candidates"]

def test_humanize():
    assert "very unique" not in humanize("This is very unique.")["text"].lower()

def test_profile_audit():
    assert "about" in profile_audit({"headline": "BI Developer"})["missing"]

def test_engager_and_thread_filters():
    assert analyze_engagers([{"title": "Recruiter"}], ["recruiter"])[0]["target_title_match"]
    assert len(thread_followups([{"author_replied": True, "reply_age_hours": 12}])) == 1

def test_advocacy():
    assert employee_advocacy_plan(5, "reach")["team_size"] == 5
