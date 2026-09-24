from app.skills.followups import FollowUp, can_schedule_followup, mark_response


def test_followup_stops_after_response():
    followup = FollowUp("Recruiter", "Thanks", "2026-09-24T10:00:00+00:00", "sent")
    assert can_schedule_followup(followup, response_received=True) is False
    mark_response(followup)
    assert followup.status == "responded"


def test_followup_can_continue_when_open():
    followup = FollowUp("Recruiter", "Checking in", "2026-09-25T10:00:00+00:00", "pending")
    assert can_schedule_followup(followup) is True
