from app.skills.jobs import (
    _clean_title,
    _location,
    _location_matches_requested,
    _normalize_posted,
)


def test_clean_title_collapses_linkedin_duplicate_title():
    assert _clean_title("Senior Developer, Power BISenior Developer, Power BI") == "Senior Developer, Power BI"


def test_normalize_posted_handles_hours_days_and_today():
    assert _normalize_posted("2 hours ago") == "2 hours ago"
    assert _normalize_posted("1 day ago") == "1 day ago"
    assert _normalize_posted("Today") == "Today"


def test_location_filter_rejects_remote_without_city():
    assert not _location_matches_requested("India (Remote)", "Gurgaon")


def test_location_filter_accepts_gurugram_alias():
    assert _location_matches_requested("Gurugram, Haryana, India (On-site)", "Gurgaon")
