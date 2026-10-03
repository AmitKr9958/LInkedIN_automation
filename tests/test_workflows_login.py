"""Unit tests for interactive login settle behaviour (no real LinkedIn)."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workflows import LOGIN_WAIT_SECONDS, SESSION_SETTLE_MS, login_check


def _make_page(*, url: str = "https://www.linkedin.com/", authenticated: bool = False):
    page = AsyncMock()
    page.url = url
    page.is_closed = MagicMock(return_value=False)
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.title = AsyncMock(return_value="LinkedIn")
    return page


def _make_browser(page):
    browser = MagicMock()
    browser.pages = [page]
    browser.new_page = AsyncMock(return_value=page)
    return browser


@pytest.mark.asyncio
async def test_login_check_returns_unauthenticated_without_wait():
    page = _make_page()
    browser = _make_browser(page)
    state = {"url": page.url, "title": "LinkedIn", "authenticated": False, "confidence": "high"}

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=browser)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.workflows.linkedin_browser", return_value=cm), patch(
        "app.workflows.current_session_state", AsyncMock(return_value=state)
    ):
        result = await login_check(wait_for_login=True, keep_open=False)

    assert result.status == "unauthenticated"
    assert result.details["authenticated"] is False


@pytest.mark.asyncio
async def test_login_check_keep_open_settles_after_auth():
    """After auth is detected, login must navigate to feed and settle before close."""
    page = _make_page(url="https://www.linkedin.com/feed/")
    browser = _make_browser(page)

    states = [
        {"url": "https://www.linkedin.com/login", "title": "Sign Up", "authenticated": False, "confidence": "high"},
        {"url": "https://www.linkedin.com/feed/", "title": "Feed | LinkedIn", "authenticated": True, "confidence": "high"},
        {"url": "https://www.linkedin.com/feed/", "title": "Feed | LinkedIn", "authenticated": True, "confidence": "high"},
        {"url": "https://www.linkedin.com/feed/", "title": "Feed | LinkedIn", "authenticated": True, "confidence": "high"},
    ]
    session_mock = AsyncMock(side_effect=states)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=browser)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.workflows.linkedin_browser", return_value=cm), patch(
        "app.workflows.current_session_state", session_mock
    ), patch("app.workflows.settings") as mock_settings:
        mock_settings.headless = True
        mock_settings.linkedin_base_url = "https://www.linkedin.com"
        result = await login_check(keep_open=True, force_headed=True)

    assert result.status == "authenticated"
    assert result.details["authenticated"] is True
    # Settling wait must be applied so the persistent profile can flush cookies.
    # Implementation may split SESSION_SETTLE_MS across multiple waits (e.g. half+half).
    wait_ms = [
        call.args[0]
        for call in page.wait_for_timeout.await_args_list
        if call.args and isinstance(call.args[0], (int, float))
    ]
    assert sum(wait_ms) >= SESSION_SETTLE_MS, (
        f"expected total settle wait >= {SESSION_SETTLE_MS}, got {wait_ms}"
    )
    # Headless must be restored after interactive login.
    assert mock_settings.headless is True
    # The post-close verification must be able to recover from the fresh
    # persistent context's about:blank page.
    assert page.goto.await_count >= 2
    assert any(
        call.args
        and call.args[0].endswith("/feed/")
        for call in page.goto.await_args_list
    )


@pytest.mark.asyncio
async def test_login_check_timeout_budget_exists():
    """Interactive login must not wait forever; budget is finite."""
    assert LOGIN_WAIT_SECONDS >= 300
    assert SESSION_SETTLE_MS >= 3000
