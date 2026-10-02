from app.skills.profile import (
    _is_valid_headline,
    _normalize_section_heading,
    _parse_top_card,
    _section_heading_matches,
)


def test_pronouns_are_not_headline():
    assert not _is_valid_headline("He/Him")
    assert not _is_valid_headline("She/Her")
    assert not _is_valid_headline("They/Them")


def test_real_headline_is_valid():
    assert _is_valid_headline(
        "Power BI Developer | Business Intelligence | SQL"
    )


def test_top_card_skips_pronouns():
    name, headline, location = _parse_top_card(
        """
        Amit Kumar
        He/Him
        Power BI Developer | Business Intelligence | SQL
        Greater Delhi Area
        """,
        "Amit Kumar",
    )
    assert name == "Amit Kumar"
    assert headline == "Power BI Developer | Business Intelligence | SQL"
    assert location == "Greater Delhi Area"


from app.skills.profile import _normalize_section_heading, _section_heading_matches


def test_section_heading_matching_tolerates_counts_and_whitespace():
    assert _normalize_section_heading("  Experience\u00a0") == "experience"
    assert _section_heading_matches("Experience", "experience")
    assert _section_heading_matches("Skills (25)", "skills")
    assert _section_heading_matches("Experience 4", "experience")
    assert _section_heading_matches("Featured", "featured")


def test_section_heading_matching_rejects_unrelated_sections():
    assert not _section_heading_matches("Education", "experience")
    assert not _section_heading_matches("Professional Experience", "experience")


def test_extract_section_from_rendered_text():
    from app.skills.profile import _extract_section_from_text

    raw = """
    About
    Power BI and BI professional with measurable reporting improvements.
    Experience
    Senior Power BI Developer
    Bill Gosling Outsourcing
    Skills
    Power BI
    DAX
    SQL
    Featured
    Portfolio dashboard
    Education
    B.Com
    """
    assert "Bill Gosling Outsourcing" in _extract_section_from_text(raw, "experience")
    assert "DAX" in _extract_section_from_text(raw, "skills")
    assert "Portfolio dashboard" in _extract_section_from_text(raw, "featured")
    assert "B.Com" not in _extract_section_from_text(raw, "featured")


def test_extract_section_handles_decorated_heading():
    from app.skills.profile import _extract_section_from_text

    raw = "Skills (25)\nPower BI\nDAX\nFeatured\nDashboard"
    assert "Power BI" in _extract_section_from_text(raw, "skills")

def test_extract_section_handles_flattened_rendered_text():
    from app.skills.profile import _extract_section_from_text

    raw = (
        "About Power BI professional "
        "Experience Experience 4 Senior Power BI Developer Bill Gosling Outsourcing "
        "Education B.Com "
        "Skills Skills (25) Power BI DAX SQL "
        "Featured Portfolio dashboard"
    )
    experience = _extract_section_from_text(raw, "experience")
    skills = _extract_section_from_text(raw, "skills")
    featured = _extract_section_from_text(raw, "featured")
    assert "Bill Gosling Outsourcing" in experience
    assert "DAX" in skills
    assert "Portfolio dashboard" in featured
    assert "B.Com" not in experience


# ---- authenticated /details fallback (all browser objects are fakes) ----

import asyncio

from app.config import settings
from app.skills import profile as profile_mod

SLUG_URL = "https://www.linkedin.com/in/test-user-123/"


class FakeLocator:
    def __init__(self, text, fail=False):
        self._text, self._fail = text, fail

    @property
    def first(self):
        return self

    async def inner_text(self):
        if self._fail:
            raise RuntimeError("boom")
        return self._text


class FakeDetailPage:
    def __init__(self, final_url, text="", fail_extract=False, fail_goto=False):
        self.url = final_url
        self._text, self._fail_extract, self._fail_goto = text, fail_extract, fail_goto
        self.closed = False
        self.goto_url = None

    async def goto(self, url, **kwargs):
        self.goto_url = url
        if self._fail_goto:
            raise RuntimeError("nav failed")

    async def wait_for_timeout(self, ms):
        return None

    def locator(self, selector):
        return FakeLocator(self._text, self._fail_extract)

    async def close(self):
        self.closed = True


class FakeContext:
    def __init__(self, detail_page):
        self.detail_page = detail_page
        self.pages_created = 0

    async def new_page(self):
        self.pages_created += 1
        return self.detail_page


class FakeMainPage:
    def __init__(self, context):
        self.context = context


def _run(section, detail_page, monkeypatch, profile_url=SLUG_URL, with_context=True):
    monkeypatch.setattr(settings, "profile_url", profile_url)

    async def no_scroll(page, max_rounds=24):
        return None

    monkeypatch.setattr(profile_mod, "_scroll_profile_to_bottom", no_scroll)
    ctx = FakeContext(detail_page)
    main = FakeMainPage(ctx if with_context else None)
    result = asyncio.run(profile_mod._read_profile_details_page(main, section))
    return result, ctx


def test_details_route_mapping(monkeypatch):
    for section, path in {
        "experience": "/details/experience/",
        "skills": "/details/skills/",
        "featured": "/details/featured/",
    }.items():
        url = f"https://www.linkedin.com/in/test-user-123{path}"
        page = FakeDetailPage(url, text="Team Lead Acme Corp 2020 - Present " * 3)
        result, _ = _run(section, page, monkeypatch)
        assert page.goto_url == url
        assert result


def test_unsupported_section_does_not_navigate(monkeypatch):
    page = FakeDetailPage(SLUG_URL)
    result, ctx = _run("education", page, monkeypatch)
    assert result == ""
    assert ctx.pages_created == 0


def test_missing_context_fails_safely(monkeypatch):
    result, ctx = _run("skills", FakeDetailPage(SLUG_URL), monkeypatch, with_context=False)
    assert result == ""
    assert ctx.pages_created == 0


def test_invalid_configured_profile_url_does_not_navigate(monkeypatch):
    result, ctx = _run("skills", FakeDetailPage(SLUG_URL), monkeypatch, profile_url="https://evil.com/in/x/")
    assert result == ""
    assert ctx.pages_created == 0


def test_unexpected_redirects_rejected(monkeypatch):
    bad_urls = [
        "https://www.linkedin.com/authwall?trk=x",
        "https://www.linkedin.com/login",
        "https://www.linkedin.com/checkpoint/challenge/abc",
        "https://www.linkedin.com/in/someone-else/details/skills/",
        "https://www.linkedin.com/in/test-user-123/",
        "https://www.linkedin.com/in/test-user-123/details/experience/",
        "https://evil.com/in/test-user-123/details/skills/",
        "http://www.linkedin.com/in/test-user-123/details/skills/",
    ]
    for url in bad_urls:
        page = FakeDetailPage(url, text="Python DAX SQL Power BI " * 5)
        result, _ = _run("skills", page, monkeypatch)
        assert result == "", url
        assert page.closed


def test_correct_url_accepted_case_insensitive(monkeypatch):
    page = FakeDetailPage(
        "https://in.linkedin.com/in/Test-User-123/details/skills",
        text="Power BI DAX SQL Power Query Data Modeling",
    )
    result, _ = _run("skills", page, monkeypatch)
    assert "DAX" in result


def test_temp_page_closed_on_extraction_failure(monkeypatch):
    page = FakeDetailPage(
        "https://www.linkedin.com/in/test-user-123/details/skills/", fail_extract=True
    )
    result, _ = _run("skills", page, monkeypatch)
    assert result == ""
    assert page.closed


def test_temp_page_closed_on_navigation_failure(monkeypatch):
    page = FakeDetailPage(SLUG_URL, fail_goto=True)
    result, _ = _run("skills", page, monkeypatch)
    assert result == ""
    assert page.closed


def test_temp_page_closed_on_success(monkeypatch):
    page = FakeDetailPage(
        "https://www.linkedin.com/in/test-user-123/details/skills/",
        text="Power BI DAX SQL Power Query Data Modeling",
    )
    _run("skills", page, monkeypatch)
    assert page.closed


def test_scoped_page_without_heading_is_used(monkeypatch):
    page = FakeDetailPage(
        "https://www.linkedin.com/in/test-user-123/details/experience/",
        text="Team Leader Acme Outsourcing Mar 2022 - Jul 2026 Led analysts",
    )
    result, _ = _run("experience", page, monkeypatch)
    assert "Team Leader" in result


def test_noise_below_content_is_cut_and_short_content_rejected(monkeypatch):
    page = FakeDetailPage(
        "https://www.linkedin.com/in/test-user-123/details/skills/",
        text="Power BI DAX SQL Power Query Data Modeling More profiles for you Random Person",
    )
    result, _ = _run("skills", page, monkeypatch)
    assert "Random Person" not in result and "DAX" in result

    tiny = FakeDetailPage(
        "https://www.linkedin.com/in/test-user-123/details/skills/", text="Skills"
    )
    result, _ = _run("skills", tiny, monkeypatch)
    assert result == ""


def test_read_profile_section_invokes_details_fallback(monkeypatch):
    class EmptyLocator:
        @property
        def first(self):
            return self

        async def count(self):
            return 0

        async def inner_text(self):
            return ""

    class Page:
        def locator(self, selector):
            return EmptyLocator()

        async def evaluate(self, *args, **kwargs):
            raise RuntimeError("no DOM match")

    async def fake_details(page, section_name):
        assert section_name == "experience"
        return "Senior Power BI Developer at Acme"

    monkeypatch.setattr(profile_mod, "_read_profile_details_page", fake_details)
    result = asyncio.run(profile_mod._read_profile_section(Page(), "experience"))
    assert result == "Senior Power BI Developer at Acme"


from app.skills.profile import _clean_profile_section_text, _extract_section_from_text


def test_profile_section_cleaner_removes_linkedin_recommendation_noise():
    raw = (
        "Experience Business Intelligence Team Lead · Power BI · SQL "
        "Built dashboards and improved refresh time by 75%. "
        "Who your viewers also viewed Hitarth Patel · 2nd Power BI | Connect "
        "Subir Bairagi · 2nd Data Analyst"
    )
    cleaned = _clean_profile_section_text(raw, "experience")
    assert "Business Intelligence Team Lead" in cleaned
    assert "75%" in cleaned
    assert "Who your viewers also viewed" not in cleaned
    assert "Hitarth Patel" not in cleaned
    assert "Subir Bairagi" not in cleaned


def test_section_extractor_stops_at_recommendation_noise():
    raw = """Experience
Business Intelligence Team Lead
Built Power BI dashboards and improved refresh time by 75%.
Who your viewers also viewed
Hitarth Patel · 2nd
Skills
Power BI
SQL
"""
    extracted = _extract_section_from_text(raw, "experience")
    assert "Business Intelligence Team Lead" in extracted
    assert "75%" in extracted
    assert "Who your viewers also viewed" not in extracted
    assert "Hitarth Patel" not in extracted
    assert "Skills" not in extracted


def test_about_edit_dialog_reads_value_and_closes_without_save():
    from app.skills.profile import _read_about_from_edit_dialog

    class Keyboard:
        def __init__(self):
            self.pressed = []

        async def press(self, key):
            self.pressed.append(key)

    class Page:
        def __init__(self):
            self.keyboard = Keyboard()
            self.calls = 0

        async def evaluate(self, script, *args):
            self.calls += 1
            if self.calls == 1:
                # The selector logic itself runs in the browser; this fake only
                # verifies that the helper performs a click/read/close sequence.
                assert "edit" in script.lower()
                return True
            assert "textarea" in script
            return "When a dashboard takes 8 seconds to load, executives stop trusting it. I make them load in 2."

        async def wait_for_timeout(self, ms):
            return None

    page = Page()
    result = asyncio.run(_read_about_from_edit_dialog(page))
    assert "8 seconds" in result
    assert "I make them load in 2" in result
    assert page.keyboard.pressed == ["Escape"]


def test_about_edit_dialog_uses_icon_only_fallback_without_save():
    from app.skills.profile import _read_about_from_edit_dialog

    class Keyboard:
        async def press(self, key):
            assert key == "Escape"

    class Page:
        keyboard = Keyboard()
        calls = 0

        async def evaluate(self, script, *args):
            self.calls += 1
            if self.calls == 1:
                assert "about" in script.lower()
                return True
            assert "textarea" in script
            return "Full About content from the LinkedIn editor."

        async def wait_for_timeout(self, ms):
            return None

    result = asyncio.run(_read_about_from_edit_dialog(Page()))
    assert result == "Full About content from the LinkedIn editor."


def test_about_edit_dialog_playwright_locator_is_preferred():
    from app.skills.profile import _read_about_from_edit_dialog

    class Candidate:
        async def get_attribute(self, name):
            return "Edit About" if name == "aria-label" else None

        async def inner_text(self):
            return ""

        async def click(self, timeout=None):
            return None

    class Candidates:
        async def count(self):
            return 1

        def nth(self, index):
            return Candidate()

    class Keyboard:
        async def press(self, key):
            assert key == "Escape"

    class Page:
        keyboard = Keyboard()

        def locator(self, selector):
            assert 'aria-label*="edit"' in selector
            return Candidates()

        async def wait_for_timeout(self, ms):
            return None

        async def evaluate(self, script, *args):
            assert "textarea" in script
            return "Complete About text read from the editor."

    result = asyncio.run(_read_about_from_edit_dialog(Page()))
    assert result == "Complete About text read from the editor."
