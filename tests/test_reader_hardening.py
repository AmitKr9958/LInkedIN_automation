import json
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
    Job,
    _POSTED_RE,
    _attribute_text,
    _company_from_page_title,
    _detail_company_from_links,
    _detail_fields,
    _fallback_company,
    _hours_from_datetime,
    _hours_from_posted,
    _jsonld_job_fields,
    _location_from_detail_text,
    _logo_company,
    _merge_detail,
    _normalize_posted,
    _relative_from_datetime,
    search,
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


def test_normalize_posted_supports_all_live_variants():
    expected = {
        "Just now": "Just now",
        "1 minute ago": "1 minute ago",
        "15 minutes ago": "15 minutes ago",
        "1 hour ago": "1 hour ago",
        "22 hours ago": "22 hours ago",
        "1 day ago": "1 day ago",
        "2 days ago": "2 days ago",
        "1 week ago": "1 week ago",
        "2 weeks ago": "2 weeks ago",
        "1 month ago": "1 month ago",
        "30+ days ago": "30+ days ago",
        "Today": "Today",
        "Yesterday": "Yesterday",
    }
    for raw, normalized in expected.items():
        assert _normalize_posted(raw) == normalized, raw


def test_hours_from_posted_maps_variants_to_numeric_recency():
    assert _hours_from_posted("Just now") == 0.0
    assert _hours_from_posted("Today") == 0.0
    assert _hours_from_posted("Yesterday") == 24.0
    assert _hours_from_posted("15 minutes ago") == 0.25
    assert _hours_from_posted("22 hours ago") == 22.0
    assert _hours_from_posted("2 days ago") == 48.0
    assert _hours_from_posted("1 week ago") == 168.0
    assert _hours_from_posted("1 month ago") == 720.0
    assert _hours_from_posted("30+ days ago") == 720.0
    assert _hours_from_posted("") is None
    assert _hours_from_posted("Easy Apply") is None


def test_relative_datetime_keeps_hour_level_precision():
    now = datetime.now(timezone.utc)
    assert _relative_from_datetime(
        (now - timedelta(minutes=15)).isoformat()
    ) == "15 minutes ago"
    assert _relative_from_datetime((now - timedelta(hours=1)).isoformat()) == "1 hour ago"
    assert _relative_from_datetime((now - timedelta(hours=22)).isoformat()) == "22 hours ago"
    assert _relative_from_datetime((now - timedelta(days=16)).isoformat()) == "2 weeks ago"
    assert _relative_from_datetime((now - timedelta(days=40)).isoformat()) == "1 month ago"


def test_hours_from_datetime_tracks_recency():
    now = datetime.now(timezone.utc)
    hours = _hours_from_datetime((now - timedelta(hours=18)).isoformat())
    assert hours is not None
    assert 17.9 < hours < 18.1
    assert _hours_from_datetime("not-a-date") is None


class _AttrLocator:
    def __init__(self, attrs):
        self._attrs = attrs

    async def get_attribute(self, name):
        return self._attrs.get(name)


async def test_attribute_text_reads_accessibility_values():
    assert await _attribute_text(_AttrLocator({"aria-label": " 22 hours ago "})) == "22 hours ago"
    assert await _attribute_text(_AttrLocator({"title": "1 week ago"})) == "1 week ago"
    assert await _attribute_text(
        _AttrLocator({"datetime": "2026-09-24T06:00:00Z"})
    ) == "2026-09-24T06:00:00Z"
    assert await _attribute_text(_AttrLocator({})) == ""


def _jobposting_jsonld(date_hours_ago: float, company: str = "Example Corp", location: str = "") -> str:
    payload = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Power BI Developer",
        "datePosted": (
            datetime.now(timezone.utc) - timedelta(hours=date_hours_ago)
        ).isoformat(),
        "hiringOrganization": {"@type": "Organization", "name": company},
    }
    if location:
        payload["jobLocation"] = {
            "@type": "Place",
            "address": {"@type": "PostalAddress", "addressLocality": location},
        }
    return json.dumps(payload)


def test_jsonld_job_fields_extract_company_and_posted():
    fields = _jsonld_job_fields([_jobposting_jsonld(18), "not-json", ""])
    assert fields["company"] == "Example Corp"
    assert fields["posted"] == "18 hours ago"
    assert fields["posted_hours"] is not None
    assert 17.9 < fields["posted_hours"] < 18.1


def test_jsonld_job_fields_extract_location():
    fields = _jsonld_job_fields([_jobposting_jsonld(18, location="Gurugram")])
    assert fields["location"] == "Gurugram"


def test_jsonld_job_fields_tolerate_missing_data():
    empty = {"company": "", "posted": "", "posted_hours": None, "location": ""}
    assert _jsonld_job_fields([]) == empty
    assert _jsonld_job_fields(["{}"]) == empty


class _DetailNode:
    def __init__(self, text="", attrs=None):
        self._text = text
        self._attrs = attrs or {}

    @property
    def first(self):
        return self

    async def count(self):
        return 1 if (self._text or self._attrs) else 0

    async def text_content(self):
        return self._text

    async def inner_text(self):
        return self._text

    async def get_attribute(self, name):
        return self._attrs.get(name)


class _CompanyLinks:
    def __init__(self, texts):
        self._texts = list(texts)

    async def count(self):
        return len(self._texts)

    def nth(self, index):
        return _DetailNode(self._texts[index])


class _DetailPage:
    """Minimal page double for the targeted detail-page extraction path."""

    def __init__(
        self,
        company="",
        posted="",
        jsonld=None,
        company_links=None,
        body_text="",
        title_text="",
        location="",
    ):
        self.company = company
        self.posted = posted
        self.jsonld = jsonld or []
        self.company_links = company_links or []
        self.body_text = body_text
        self.title_text = title_text
        self.location = location
        self.visited = []

    async def goto(self, url, wait_until=None):
        self.visited.append(url)

    async def wait_for_timeout(self, ms):
        return None

    async def evaluate(self, script):
        return self.jsonld

    async def title(self):
        return self.title_text

    async def inner_text(self, selector="body"):
        return self.body_text

    def locator(self, selector):
        from app.skills.jobs import (
            DETAIL_COMPANY_SELECTORS,
            DETAIL_LOCATION_SELECTORS,
            DETAIL_POSTED_SELECTORS,
        )

        if selector in DETAIL_COMPANY_SELECTORS:
            return _DetailNode(self.company)
        if selector in DETAIL_LOCATION_SELECTORS and self.location:
            return _DetailNode(self.location)
        if selector in DETAIL_POSTED_SELECTORS:
            return _DetailNode(self.posted)
        if selector == "a[href*='/company/']":
            return _CompanyLinks(self.company_links)
        if selector == "main":
            return _DetailNode(self.body_text)
        return _DetailNode()


async def test_detail_fields_extract_company_and_posted_from_page():
    page = _DetailPage(
        company="Example Corp",
        posted="India · 18 hours ago · Over 100 applicants",
    )
    fields = await _detail_fields(page, "https://www.linkedin.com/jobs/view/999")
    assert page.visited == ["https://www.linkedin.com/jobs/view/999"]
    assert fields["company"] == "Example Corp"
    assert fields["posted"] == "18 hours ago"
    assert fields["posted_hours"] == 18.0


async def test_detail_fields_use_jsonld_when_selectors_are_empty():
    page = _DetailPage(jsonld=[_jobposting_jsonld(18, company="Example Corp")])
    fields = await _detail_fields(page, "https://www.linkedin.com/jobs/view/1000")
    assert fields["company"] == "Example Corp"
    assert fields["posted"] == "18 hours ago"
    assert fields["posted_hours"] is not None
    assert 17.9 < fields["posted_hours"] < 18.1


async def test_detail_fields_survive_navigation_errors():
    class _BrokenPage:
        async def goto(self, url, wait_until=None):
            raise RuntimeError("navigation failed")

    fields = await _detail_fields(_BrokenPage(), "https://www.linkedin.com/jobs/view/1")
    assert fields == {"company": "", "posted": "", "posted_hours": None, "location": ""}


def test_merge_detail_fills_only_missing_card_fields():
    # Regression: the live Business Intelligence Manager card exposed only
    # title and location; company and posted came back from the detail page.
    job = Job(
        title="Business Intelligence Manager",
        location="Gurugram, Haryana, India (Hybrid)",
    )
    _merge_detail(
        job,
        {"company": "Example Corp", "posted": "18 hours ago", "posted_hours": 18.0},
    )
    assert job.company == "Example Corp"
    assert job.posted == "18 hours ago"
    assert job.posted_hours == 18.0


def test_merge_detail_keeps_existing_card_values():
    job = Job(
        title="Power BI Developer",
        company="Card Corp",
        posted="22 hours ago",
        posted_hours=22.0,
    )
    _merge_detail(
        job,
        {"company": "Detail Corp", "posted": "1 day ago", "posted_hours": 24.0},
    )
    assert job.company == "Card Corp"
    assert job.posted == "22 hours ago"
    assert job.posted_hours == 22.0


async def test_detail_company_from_links_skips_empty_and_call_to_action():
    page = _DetailPage(company_links=["", "   ", "Show Premium Insights", "Guardian"])
    assert await _detail_company_from_links(page) == "Guardian"
    assert await _detail_company_from_links(_DetailPage()) == ""


def test_company_from_page_title_parses_tab_title():
    assert (
        _company_from_page_title("Lead - Reporting & Analytics | Guardian | LinkedIn")
        == "Guardian"
    )
    assert _company_from_page_title("Business Intelligence Manager | LinkedIn") == ""
    assert _company_from_page_title("") == ""


async def test_detail_fields_use_company_links_and_main_text():
    # Live regression: the 2026 detail DOM exposes the company as the top-card
    # company link and the posted label inside the main text top-card region.
    page = _DetailPage(
        company_links=["Guardian", "Guardian", "Show Premium Insights"],
        body_text=(
            "Guardian Lead - Reporting & Analytics Gurgaon, Haryana, India "
            "\u00b7 23 hours ago \u00b7 Over 100 people clicked apply"
        ),
    )
    fields = await _detail_fields(page, "https://www.linkedin.com/jobs/view/4469335122")
    assert fields["company"] == "Guardian"
    assert fields["posted"] == "23 hours ago"
    assert fields["posted_hours"] == 23.0


async def test_detail_fields_fall_back_to_page_title_for_company():
    page = _DetailPage(
        title_text="Senior Developer, Power BI | Hollister Incorporated | LinkedIn",
        body_text=(
            "Senior Developer, Power BI Gurugram, Haryana, India "
            "\u00b7 2 weeks ago \u00b7 Over 100 people clicked apply"
        ),
    )
    fields = await _detail_fields(page, "https://www.linkedin.com/jobs/view/4464444518")
    assert fields["company"] == "Hollister Incorporated"
    assert fields["posted"] == "2 weeks ago"
    assert fields["posted_hours"] == 336.0


async def test_detail_fields_leave_company_unknown_when_linkedin_hides_it():
    # Promoted/off-LinkedIn-managed postings expose no structured company;
    # the record must stay explicitly unknown rather than guessing.
    page = _DetailPage(
        body_text=(
            "Business Intelligence Manager Gurugram, Haryana, India "
            "\u00b7 1 week ago \u00b7 Over 100 people clicked apply Promoted by hirer"
        ),
    )
    fields = await _detail_fields(page, "https://www.linkedin.com/jobs/view/4464774817")
    assert fields["company"] == ""
    assert fields["posted"] == "1 week ago"
    assert fields["posted_hours"] == 168.0


def test_location_from_detail_text_variants():
    body = (
        "Business Intelligence Manager Gurugram, Haryana, India "
        "\u00b7 1 week ago \u00b7 Over 100 people clicked apply"
    )
    assert _location_from_detail_text(body, "Business Intelligence Manager") == "Gurugram, Haryana, India"
    assert _location_from_detail_text(body, "") == "Gurugram, Haryana, India"
    assert _location_from_detail_text("India (Remote)", "") == "India (Remote)"
    assert _location_from_detail_text("Apply now", "") == ""
    assert _location_from_detail_text("", "Power BI Developer") == ""


async def test_detail_fields_extract_location_from_main_text():
    page = _DetailPage(
        body_text=(
            "Business Intelligence Manager Gurugram, Haryana, India "
            "\u00b7 18 hours ago \u00b7 Over 100 applicants"
        )
    )
    fields = await _detail_fields(
        page,
        "https://www.linkedin.com/jobs/view/404",
        title="Business Intelligence Manager",
    )
    assert fields["location"] == "Gurugram, Haryana, India"
    assert fields["posted"] == "18 hours ago"
    assert fields["posted_hours"] == 18.0


def test_merge_detail_fills_missing_location():
    job = Job(title="Power BI Developer")
    _merge_detail(
        job,
        {
            "company": "Example Corp",
            "posted": "1 hour ago",
            "posted_hours": 1.0,
            "location": "Gurugram, Haryana, India",
        },
    )
    assert job.location == "Gurugram, Haryana, India"


def test_job_records_carry_source():
    assert Job("Power BI Developer").source == "linkedin"
    assert Job("Power BI Developer").to_dict()["source"] == "linkedin"


# --- search-level stage diagnostics (safe counters, no session data) ---


class _NodeList:
    """Locator-shaped list supporting nth/first/count as real Playwright does."""

    def __init__(self, nodes):
        self._nodes = list(nodes)

    @property
    def first(self):
        return self._nodes[0] if self._nodes else _DetailNode()

    async def count(self):
        return len(self._nodes)

    def nth(self, index):
        return self._nodes[index]

    async def wait_for(self, state=None, timeout=None):
        return None


def _node(text="", href=""):
    return _DetailNode(text, {"href": href} if href else None)


class _SearchCard:
    """Card double covering the locator surface jobs.search() touches."""

    def __init__(self, text="", href="", title="", company="", location="", posted=""):
        self._text = text
        self._href = href
        self._title = title
        self._company = company
        self._location = location
        self._posted = posted

    async def inner_text(self):
        return self._text

    async def get_attribute(self, name):
        return self._href if name == "href" else None

    async def scroll_into_view_if_needed(self, timeout=None):
        return None

    async def wait_for(self, state=None, timeout=None):
        return None

    def locator(self, selector):
        from app.skills.jobs import (
            COMPANY_SELECTORS,
            EASY_APPLY_SELECTORS,
            LOCATION_SELECTORS,
            POSTED_SELECTORS,
            TITLE_SELECTORS,
        )

        if selector == "a[href*='/jobs/']":
            return _NodeList([_node(href=self._href)] if self._href else [])
        if selector == "time[datetime]":
            return _NodeList([])
        if selector in TITLE_SELECTORS:
            return _NodeList([_node(self._title)] if self._title else [])
        if selector in COMPANY_SELECTORS:
            return _NodeList([_node(self._company)] if self._company else [])
        if selector in LOCATION_SELECTORS:
            return _NodeList([_node(self._location)] if self._location else [])
        if selector in POSTED_SELECTORS:
            return _NodeList([_node(self._posted)] if self._posted else [])
        if selector in EASY_APPLY_SELECTORS:
            return _NodeList([])
        return _NodeList([])


class _SearchPage:
    """Page double for jobs.search() including the detail-hydration path."""

    def __init__(self, cards, detail_body="", title_text=""):
        self._cards = list(cards)
        self.detail_body = detail_body
        self.title_text = title_text
        self.visited = []

    async def goto(self, url, wait_until=None, timeout=None):
        self.visited.append(url)

    async def wait_for_timeout(self, ms):
        return None

    async def title(self):
        return self.title_text

    async def evaluate(self, script):
        return []

    async def inner_text(self, selector="body"):
        return self.detail_body

    def locator(self, selector):
        from app.skills.jobs import (
            CARD_SELECTORS,
            DETAIL_COMPANY_SELECTORS,
            DETAIL_LOCATION_SELECTORS,
            DETAIL_POSTED_SELECTORS,
        )

        if selector in CARD_SELECTORS:
            return _NodeList(self._cards)
        if selector in DETAIL_COMPANY_SELECTORS:
            return _NodeList([])
        if selector in DETAIL_LOCATION_SELECTORS:
            return _NodeList([])
        if selector in DETAIL_POSTED_SELECTORS:
            return _NodeList([])
        if selector == "main":
            return _NodeList([_node(self.detail_body)] if self.detail_body else [])
        return _NodeList([])


async def test_search_reports_stage_diagnostics():
    good = _SearchCard(
        text="Power BI Developer Example Corp Gurgaon, Haryana, India 1 hour ago",
        href="https://www.linkedin.com/jobs/view/101",
        title="Power BI Developer",
        company="Example Corp",
        location="Gurgaon, Haryana, India (On-site)",
        posted="1 hour ago",
    )
    duplicate = _SearchCard(
        text="Power BI Developer Example Corp Gurgaon, Haryana, India 1 hour ago",
        href="https://www.linkedin.com/jobs/view/101/?trk=copy",
        title="Power BI Developer",
        company="Example Corp",
        location="Gurgaon, Haryana, India (On-site)",
        posted="1 hour ago",
    )
    remote = _SearchCard(
        text="Data Analyst Beta India (Remote) 1 day ago",
        href="https://www.linkedin.com/jobs/view/202",
        title="Data Analyst",
        company="Beta",
        location="India (Remote)",
        posted="1 day ago",
    )
    page = _SearchPage([good, duplicate, remote])
    diagnostics = {}
    result = await search(page, "Power BI Developer", "Gurgaon", diagnostics=diagnostics)
    assert len(result) == 1
    assert result[0].source == "linkedin"
    assert diagnostics["cards_detected"] == 3
    assert diagnostics["urls_extracted"] == 3
    assert diagnostics["titles_extracted"] == 3
    assert diagnostics["companies_extracted"] == 3
    assert diagnostics["locations_extracted"] == 3
    assert diagnostics["posted_extracted"] == 3
    assert diagnostics["rejected_duplicate"] == 1
    assert diagnostics["rejected_location"] == 1
    assert diagnostics["returned"] == 1


async def test_search_hydrates_location_from_detail_page_before_location_filter():
    # Live regression: SDUI cards can render without a location line while the
    # detail page still shows it; hydration must run before the location filter.
    card = _SearchCard(
        text="Power BI Developer Example Corp 2 hours ago",
        href="https://www.linkedin.com/jobs/view/303",
        title="Power BI Developer",
        company="Example Corp",
        posted="2 hours ago",
    )
    page = _SearchPage(
        [card],
        detail_body=(
            "Power BI Developer Gurugram, Haryana, India "
            "\u00b7 2 hours ago \u00b7 Over 100 applicants"
        ),
    )
    diagnostics = {}
    result = await search(page, "Power BI", "Gurgaon", diagnostics=diagnostics)
    assert len(result) == 1
    assert result[0].location == "Gurugram, Haryana, India"
    assert diagnostics["detail_pages_visited"] == 1
    assert diagnostics["location_filled_from_detail"] == 1
    assert diagnostics.get("rejected_location", 0) == 0
    assert diagnostics["returned"] == 1
