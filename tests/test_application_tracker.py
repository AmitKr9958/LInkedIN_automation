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
