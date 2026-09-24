from app.content_skills import (
    analyze_engagers, content_plan, draft_comment, draft_reply, extract_hook,
    humanize, interviewer_questions, profile_audit, repurpose, thread_followups,
    employee_advocacy_plan, write_post,
)
from app.post_audit import audit_post
from app.voice import audit_voice

def test_content_plan_bounded():
    assert len(content_plan("Power BI", "recruiters", 40)) == 31

def test_extract_hook():
    assert "number" in extract_hook("3 lessons I learned\nMore")["candidates"]

def test_humanize():
    assert "very unique" not in humanize("This is very unique.")["text"].lower()

def test_profile_audit():
    assert "about" in profile_audit({"headline": "BI Developer"})["missing"]

def test_post_audit_and_voice():
    result = audit_post("I reduced refresh time by 20%.\n\nWhat would you change?")
    assert result["checks"]["has_specific_number"]
    assert "metrics" in audit_voice("A 20% improvement was measured.")

def test_engager_and_thread_filters():
    assert analyze_engagers([{"title": "Recruiter"}], ["recruiter"])[0]["target_title_match"]
    assert len(thread_followups([{"author_replied": True, "reply_age_hours": 12}])) == 1

def test_advocacy():
    assert employee_advocacy_plan(5, "reach")["team_size"] == 5

def test_write_post_draft_only_with_empty_fallback():
    draft = write_post("Power BI", "Share a dashboard win")
    assert draft.kind == "post"
    assert "Power BI" in draft.text
    assert draft.metadata["topic"] == "Power BI"
    assert "voice_audit" in draft.metadata
    assert write_post("", "").kind == "post"

def test_repurpose_preserves_source_text():
    draft = repurpose("Dashboards should answer one question. Everything else is noise.")
    assert draft.kind == "repurposed_post"
    assert "one question" in draft.text
    assert draft.metadata["goal"] == "engagement"
    assert "voice_audit" in draft.metadata
    assert repurpose("").kind == "repurposed_post"

def test_draft_comment_handles_short_and_long_context():
    short = draft_comment("Short post", "Great breakdown")
    assert short.kind == "comment"
    assert "Great breakdown" in short.text
    assert short.metadata["source"] == "Short post"
    assert draft_comment("word " * 500, "A point").kind == "comment"

def test_draft_reply_returns_supplied_response_safely():
    draft = draft_reply("Do you use DAX daily?", "Yes, for measures.")
    assert draft.kind == "reply"
    assert draft.text == "Yes, for measures."
    assert draft.metadata["in_reply_to"] == "Do you use DAX daily?"
    assert draft_reply("", "").kind == "reply"

def test_interviewer_questions_cover_topic_and_empty():
    questions = interviewer_questions("Power BI")
    assert len(questions) == 5
    assert "Power BI" in questions[0]
    assert len(interviewer_questions("")) == 5
