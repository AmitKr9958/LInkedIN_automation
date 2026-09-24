from datetime import datetime, timedelta, timezone

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


def test_clean_title_removes_concatenated_duplicate_rendering():
    # Live cards sometimes concatenate the duplicate title with no separator.
    assert _clean_title(
        "Business Intelligence ManagerBusiness Intelligence Manager"
    ) == "Business Intelligence Manager"
    assert _clean_title(
        "Data Visualization Specialist (Remote)Data Visualization Specialist (Remote)"
    ) == "Data Visualization Specialist (Remote)"


def test_profile_name_can_fall_back_to_linkedin_title():
    assert _name_from_title("Amit Kumar | LinkedIn") == "Amit Kumar"
    assert _name_from_title("Feed | LinkedIn") == ""


from app.skills.jobs import (
    _POSTED_RE,
    _fallback_company,
    _logo_company,
    _normalize_posted,
    _relative_from_datetime,
)
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


def test_normalize_posted_strips_suffix_and_normalizes_just_now():
    assert _normalize_posted("21 hours ago Within the past 24 hours") == "21 hours ago"
    assert _normalize_posted("just now") == "Just now"
    assert _normalize_posted("1 month ago") == "1 month ago"


def test_normalize_posted_rejects_non_time_text():
    # Selector fallbacks can return badges such as "Easy Apply"; those must
    # never leak into the posted field.
    assert _normalize_posted("Easy Apply") == ""
    assert _normalize_posted("Viewed Promoted") == ""
    assert _normalize_posted("") == ""


def test_relative_datetime_fallback_converts_dates():
    now = datetime.now(timezone.utc)
    assert _relative_from_datetime(now.isoformat()) == "Just now"
    assert _relative_from_datetime((now - timedelta(days=3)).isoformat()) == "3 days ago"
    assert _relative_from_datetime("not-a-date") == ""


def test_fallback_company_skips_alumni_and_state_noise():
    raw = """Business Intelligence Manager
Business Intelligence Manager
Gurugram, Haryana, India (Hybrid)
18 school alumni work here
18 Delhi University school alumni work here
Promoted"""
    assert _fallback_company(
        raw,
        "Business Intelligence Manager",
        "Gurugram, Haryana, India (Hybrid)",
        "",
    ) == ""


class _FakeLocator:
    def __init__(self, alt):
        self._alt = alt

    @property
    def first(self):
        return self

    async def count(self):
        return 1 if self._alt is not None else 0

    async def get_attribute(self, name):
        return self._alt if name == "alt" else None


class _FakeCard:
    def __init__(self, alt):
        self._alt = alt

    def locator(self, selector):
        return _FakeLocator(self._alt)


async def test_logo_company_extracts_alt_and_skips_placeholder():
    assert await _logo_company(_FakeCard("EXL logo")) == "EXL"
    assert await _logo_company(_FakeCard("Quik Hire Staffing logo")) == "Quik Hire Staffing"
    assert await _logo_company(_FakeCard("{:companyName} logo")) == ""
    assert await _logo_company(_FakeCard(None)) == ""
