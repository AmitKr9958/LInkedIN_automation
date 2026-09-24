from app.skills.followups import FollowUp, can_schedule_followup, list_followups, make_followup, mark_response, transition_followup


def test_followup_stops_after_response(tmp_path):
    followup = FollowUp("Recruiter", "Thanks", "2026-09-24T10:00:00+00:00", "sent")
    assert can_schedule_followup(followup, response_received=True) is False
    mark_response(followup, path=tmp_path / "activity.sqlite3")
    assert followup.status == "responded"
    assert can_schedule_followup(followup) is False


def test_followup_can_continue_when_open():
    followup = FollowUp("Recruiter", "Checking in", "2026-09-25T10:00:00+00:00", "pending")
    assert can_schedule_followup(followup) is True


def test_followup_persists_message_and_current_status(tmp_path):
    path = tmp_path / "activity.sqlite3"
    created = make_followup("Recruiter", "Checking in", "2030-01-01T00:00:00+00:00", path=path)
    assert created.message == "Checking in"
    transition_followup(created, "sent", path=path)
    rows = list_followups(path=path)
    assert len(rows) == 1
    assert rows[0].message == "Checking in"
    assert rows[0].status == "sent"


def test_followup_response_is_terminal_in_persistence(tmp_path):
    path = tmp_path / "activity.sqlite3"
    created = make_followup("Recruiter", "Hello", "2030-01-02T00:00:00+00:00", path=path)
    transition_followup(created, "sent", path=path)
    mark_response(created, path=path)
    rows = list_followups(path=path)
    assert rows[0].status == "responded"
    assert can_schedule_followup(rows[0]) is False
