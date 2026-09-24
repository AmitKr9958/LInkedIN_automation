from app.job_normalize import dedupe_jobs, normalize_job_url
from app.skills.jobs import _clean_title
from app.skills.profile import _name_from_title


def test_normalize_linkedin_job_url_drops_tracking_query():
    url = (
        "https://www.linkedin.com/jobs/view/123456/?"
        "eBP=abc&trackingId=def&refId=ghi&trk=flagship3_search_srp_jobs"
    )
    assert normalize_job_url(url) == "https://www.linkedin.com/jobs/view/123456"


def test_dedupe_jobs_collapses_same_linkedin_job():
    jobs = [
        {
            "title": "Senior Power BI Developer",
            "company": "EXL",
            "location": "Gurugram",
            "href": "https://www.linkedin.com/jobs/view/123/?trk=foo",
        },
        {
            "title": "Senior Power BI Developer",
            "company": "EXL",
            "location": "Gurugram",
            "href": "https://www.linkedin.com/jobs/view/123/?refId=bar",
        },
    ]
    result = dedupe_jobs(jobs)
    assert len(result) == 1
    assert result[0]["url"] == "https://www.linkedin.com/jobs/view/123"


def test_empty_jobs_are_not_all_collapsed():
    jobs = [{"title": "", "company": "", "location": ""}, {"title": "", "company": "", "location": ""}]
    assert len(dedupe_jobs(jobs)) == 2


def test_clean_title_removes_duplicate_rendering_and_verification():
    assert _clean_title(
        "Senior Power BI Developer Senior Power BI Developer with verification"
    ) == "Senior Power BI Developer"


def test_profile_name_can_fall_back_to_linkedin_title():
    assert _name_from_title("Amit Kumar | LinkedIn") == "Amit Kumar"
    assert _name_from_title("Feed | LinkedIn") == ""


from app.skills.jobs import _POSTED_RE, _fallback_company
from app.skills.profile import _parse_top_card


def test_posted_regex_extracts_relative_time():
    assert _POSTED_RE.search("Lead - Reporting & Analytics 19 hours ago") is not None


def test_fallback_company_extracts_company_from_card_text():
    raw = """Business Intelligence Manager
Business Intelligence Manager
Example Corp
Gurugram, Haryana, India (Hybrid)"""
    assert _fallback_company(
        raw,
        "Business Intelligence Manager",
        "Gurugram, Haryana, India (Hybrid)",
        "",
    ) == "Example Corp"


def test_profile_top_card_fallback_extracts_headline_and_location():
    name, headline, location = _parse_top_card(
        """Amit Kumar
Senior Power BI Developer | Business Intelligence
New Delhi, Delhi, India
500+ connections""",
        "Amit Kumar",
    )
    assert name == "Amit Kumar"
    assert headline.startswith("Senior Power BI Developer")
    assert "Delhi" in location
