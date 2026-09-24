from __future__ import annotations

from dataclasses import dataclass

from .linkedin_selectors import (
    FEED_MARKERS,
    JOB_CARD_SELECTORS,
    LOGIN_MARKERS,
    PROFILE_MARKERS,
)


@dataclass
class SelectorCheck:
    name: str
    found: bool
    detail: str = ""


async def _first_visible(page, selectors: list[str]) -> tuple[bool, str]:
    for selector in selectors:
        locator = page.locator(selector)
        try:
            if await locator.count() > 0 and await locator.first.is_visible():
                return True, selector
        except Exception:
            continue
    return False, ""


async def check_page(page) -> list[SelectorCheck]:
    url = (page.url or "").lower()
    domain_ok = "linkedin.com" in url
    login_found, login_selector = await _first_visible(page, LOGIN_MARKERS)
    feed_found, feed_selector = await _first_visible(page, FEED_MARKERS)
    profile_found, profile_selector = await _first_visible(page, PROFILE_MARKERS)
    job_found, job_selector = await _first_visible(page, JOB_CARD_SELECTORS)

    return [
        SelectorCheck(
            "linkedin-domain",
            domain_ok,
            "LinkedIn URL" if domain_ok else f"Unexpected URL: {page.url}",
        ),
        SelectorCheck(
            "login-form",
            login_found,
            login_selector or "No known login marker visible",
        ),
        SelectorCheck(
            "main-content",
            feed_found,
            feed_selector or "No known authenticated feed marker visible",
        ),
        SelectorCheck(
            "job-card",
            job_found,
            job_selector or "No known job-card marker visible",
        ),
        SelectorCheck(
            "profile-heading",
            profile_found,
            profile_selector or "No known profile marker visible",
        ),
    ]
