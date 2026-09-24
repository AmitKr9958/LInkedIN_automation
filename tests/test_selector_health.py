import pytest

from app.linkedin_reader import current_session_state


class Locator:
    def __init__(self, visible=False):
        self._visible = visible

    @property
    def first(self):
        return self

    async def count(self):
        return 1

    async def is_visible(self):
        return self._visible


class Page:
    def __init__(self, url, visible_selectors=None, page_title="LinkedIn"):
        self.url = url
        self.visible_selectors = set(visible_selectors or [])
        self.page_title = page_title

    async def title(self):
        return self.page_title

    def locator(self, selector):
        return Locator(selector in self.visible_selectors)


@pytest.mark.asyncio
async def test_selector_health():
    from app.selector_health import check_page

    class HealthPage:
        url = "https://www.linkedin.com/feed/"

        def locator(self, selector):
            return Locator(selector != "input[type='password']")

    checks = await check_page(HealthPage())
    assert any(x.name == "linkedin-domain" and x.found for x in checks)


@pytest.mark.asyncio
async def test_session_state_rejects_unknown_non_login_page():
    state = await current_session_state(Page("https://www.linkedin.com/jobs/"))
    assert state["authenticated"] is False
    assert state["confidence"] == "low"


@pytest.mark.asyncio
async def test_session_state_rejects_login_page_even_with_generic_main_shell():
    state = await current_session_state(Page(
        "https://www.linkedin.com/",
        {"main[role='main']"},
        "LinkedIn: Log In or Sign Up",
    ))
    assert state["authenticated"] is False
    assert state["confidence"] == "high"


@pytest.mark.asyncio
async def test_session_state_rejects_login_marker_before_positive_marker():
    state = await current_session_state(Page(
        "https://www.linkedin.com/",
        {"input[name='session_key']", "nav[aria-label*='Primary']"},
    ))
    assert state["authenticated"] is False
    assert state["confidence"] == "high"


@pytest.mark.asyncio
async def test_session_state_accepts_authenticated_marker():
    state = await current_session_state(Page(
        "https://www.linkedin.com/feed/",
        {"[data-view-name='feed']"},
    ))
    assert state["authenticated"] is True
