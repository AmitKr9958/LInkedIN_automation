from app.models import JobPreferences

def test_default_job_preferences():
    p = JobPreferences()
    assert "Power BI" in p.keywords
    assert "Gurgaon" in p.locations
    assert p.posted_within_hours == 48
