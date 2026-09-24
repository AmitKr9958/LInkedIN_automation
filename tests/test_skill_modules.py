import pytest

from app.skill_registry import list_skills
import app.skills.connections as connections
import app.skills.engagement as engagement
import app.skills.followups as followups
import app.skills.leadgen as leadgen
import app.skills.messaging as messaging

def test_all_skill_modules_are_registered():
    expected = {"auth","profile","jobs","people","companies","posts","saved","connections","messaging","engagement","leadgen","followups","post_writer","content_planner","comment_drafter","reply_handler","humanizer","hook_extractor","repurposer","profile_optimizer","interviewer","engager_analytics","thread_monitor","employee_advocacy","outreach","post_audit","story_bank"}
    assert {s.name for s in list_skills()} == expected

def test_mutating_skills_are_not_auto_executed():
    skills = {s.name:s for s in list_skills()}
    for name in ("connections","messaging","engagement","followups"):
        assert skills[name].mutating is True


def _capture(monkeypatch, module):
    calls = []
    monkeypatch.setattr(module, "log_activity", lambda *args, **kwargs: calls.append(args))
    return calls


def test_draft_skills_record_activity(monkeypatch):
    conn_calls = _capture(monkeypatch, connections)
    result = connections.draft_connection("Priya", role="Power BI Developer")
    assert result["note"]  # generated from role when no note supplied
    assert conn_calls and conn_calls[0][0] == "connection_drafted"

    message_calls = _capture(monkeypatch, messaging)
    messaging.draft_message("Priya", "hello")
    assert message_calls and message_calls[0][0] == "message_drafted"

    engagement_calls = _capture(monkeypatch, engagement)
    engagement.draft_engagement("comment", "post-1", "great post")
    assert engagement_calls and engagement_calls[0][0] == "engagement_drafted"

    followup_calls = _capture(monkeypatch, followups)
    followups.make_followup("Priya", "checking in")
    assert followup_calls and followup_calls[0][0] == "followup_created"

    lead_calls = _capture(monkeypatch, leadgen)

    class _Person:
        name = "Priya"
        headline = "Power BI Recruiter"
        href = "https://www.linkedin.com/in/priya/"

    lead = leadgen.score_lead(_Person(), ["Power BI"])
    assert "Power BI" in lead.reason
    assert lead_calls and lead_calls[0][0] == "lead_scored"


def test_followup_lifecycle_is_duplicate_safe_and_validated(tmp_path):
    path = tmp_path / "activity.sqlite3"
    created = followups.make_followup("Priya", "check in", due_at="2030-01-01T00:00:00+00:00", path=path)
    assert created.status == "pending"
    duplicate = followups.make_followup("Priya", "check in", due_at="2030-01-01T00:00:00+00:00", path=path)
    records = followups.list_followups(path=path)
    assert len(records) == 1  # duplicate follow-up was not recorded again
    assert duplicate.target == "Priya"
    moved = followups.transition_followup(records[0], "drafted", path=path)
    assert moved.status == "drafted"
    with pytest.raises(ValueError):
        followups.transition_followup(moved, "bogus", path=path)
    followups.transition_followup(moved, "done", path=path)
    with pytest.raises(ValueError):
        followups.transition_followup(moved, "drafted", path=path)
