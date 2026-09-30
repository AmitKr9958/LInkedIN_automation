import pytest
from app.application_tracker import ApplicationTracker

def test_application_lifecycle(tmp_path):
    t=ApplicationTracker(str(tmp_path/"db.sqlite3"))
    t.add("job-1","Power BI Developer","Example")
    t.transition("job-1","shortlisted")
    t.transition("job-1","drafted")
    t.transition("job-1","applied")
    assert t.list()[0][3] == "applied"

def test_invalid_transition_rejected(tmp_path):
    t=ApplicationTracker(str(tmp_path/"db.sqlite3"))
    t.add("job-1")
    with pytest.raises(ValueError): t.transition("job-1","interview")

def test_same_status_is_idempotent(tmp_path):
    t=ApplicationTracker(str(tmp_path/"db.sqlite3"))
    t.add("job-1","Power BI Developer","Example")
    assert t.transition("job-1","new") is False
    assert t.list()[0][3] == "new"


def test_application_details_and_migration(tmp_path):
    t=ApplicationTracker(str(tmp_path/"db.sqlite3"))
    t.add("job-2","BI Developer","Example","new",source="LinkedIn",location="Gurgaon",resume_version="BI v3",notes="Follow up")
    t.update_details("job-2", recruiter="Jane", next_follow_up="2026-10-02", interview_date="2026-10-05", salary_notes="18 LPA")
    row=t.list()[0]
    assert row[2] == "Example"
    assert row[8] == "LinkedIn"
    assert row[9] == "Gurgaon"
    assert row[10] == "Jane"
    assert row[11] == "BI v3"
    assert row[12] == "2026-10-02"
    assert row[13] == "2026-10-05"
    assert row[14] == "18 LPA"
