from app.skills.jobs import (
    _clean_title,
    _location,
    _location_matches_requested,
    _build_jobs_search_url,
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


def test_incomplete_job_requires_title_and_href_contract():
    """Production Job records must expose title and href after parsing."""
    from app.skills.jobs import Job

    complete = Job(
        title="Power BI Developer",
        company="Comviva",
        location="Gurugram, Haryana, India (On-site)",
        href="https://www.linkedin.com/jobs/view/123",
        posted="4 months ago",
        posted_hours=2880.0,
    )
    assert complete.title
    assert complete.href
    assert complete.company

    incomplete = Job(title="", company="Comviva", href="")
    assert not incomplete.title
    assert not incomplete.href


def test_detail_hydration_prioritizes_jobs_missing_posting_age():
    from app.skills.jobs import Job, MAX_DETAIL_HYDRATION, _hydration_sort_key

    dated = Job(
        title="Power BI Developer",
        company="Example",
        location="Gurugram, Haryana, India (Hybrid)",
        href="https://www.linkedin.com/jobs/view/1",
        posted="1 day ago",
        posted_hours=24.0,
    )
    unknown_age = Job(
        title="Senior Power BI Developer",
        company="Example",
        location="Gurugram, Haryana, India (Hybrid)",
        href="https://www.linkedin.com/jobs/view/2",
    )
    assert MAX_DETAIL_HYDRATION == 12
    assert sorted([dated, unknown_age], key=_hydration_sort_key)[0] is unknown_age


def test_jobs_search_url_uses_six_hour_freshness_window():
    url = _build_jobs_search_url("Power BI", "Gurgaon", max_posted_hours=6)
    assert "f_TPR=r21600" in url


def test_jobs_search_url_omits_freshness_filter_when_disabled():
    url = _build_jobs_search_url("Power BI", "Gurgaon", max_posted_hours=None)
    assert "f_TPR=" not in url


def test_today_is_unknown_posting_age():
    from app.skills.jobs import _hours_from_posted
    assert _hours_from_posted("Just now") == 0.0
    assert _hours_from_posted("Today") is None
