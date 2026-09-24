from dataclasses import dataclass, asdict
from typing import Any
from urllib.parse import urljoin

from playwright.async_api import Page

from .linkedin_selectors import AUTHENTICATED_MARKERS, JOB_CARD_SELECTORS, LOGIN_MARKERS
from .config import settings


@dataclass
class JobListing:
    title: str = ""
    company: str = ""
    location: str = ""
    url: str = ""
    posted: str = ""
    text: str = ""


async def _visible(page: Page, selectors: list[str]) -> bool:
    for selector in selectors:
        locator = page.locator(selector)
        locator = locator.first if hasattr(locator, "first") else locator
        try:
            if await locator.count() and await locator.is_visible():
                return True
        except Exception:
            continue
    return False


async def current_session_state(page: Page) -> dict[str, Any]:
    """Return a conservative authentication assessment.

    A non-login URL is not sufficient evidence of authentication: LinkedIn can
    redirect anonymous users to public pages. We require a known authenticated
    marker and explicitly report low confidence when no marker is found.
    """
    url = page.url
    title = await page.title()
    url_lower = url.lower()
    title_lower = title.lower()
    login_title = "log in" in title_lower or "sign up" in title_lower
    on_login = "/login" in url_lower or login_title or await _visible(page, LOGIN_MARKERS)
    if on_login:
        return {"url": url, "title": title, "authenticated": False, "confidence": "high"}

    if await _visible(page, AUTHENTICATED_MARKERS):
        return {"url": url, "title": title, "authenticated": True, "confidence": "high"}

    # LinkedIn can render the authenticated feed without exposing one of the
    # older navigation selectors. A canonical /feed/ URL plus the feed title
    # is strong positive evidence, while login evidence was already checked
    # above and therefore takes precedence.
    if "/feed/" in url_lower and title_lower.startswith("feed | linkedin"):
        return {"url": url, "title": title, "authenticated": True, "confidence": "high"}

    return {"url": url, "title": title, "authenticated": False, "confidence": "low"}


async def _text(card, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        loc = card.locator(selector).first
        try:
            if await loc.count():
                value = " ".join(((await loc.text_content()) or "").split())
                if value:
                    return value
        except Exception:
            continue
    return ""


async def read_job_cards(page: Page) -> list[dict[str, Any]]:
    selector = ", ".join(JOB_CARD_SELECTORS)
    cards = await page.locator(selector).all()
    result: list[dict[str, Any]] = []
    for card in cards[:50]:
        text = " ".join((await card.inner_text()).split())
        href = ""
        link = card.locator("a[href*='/jobs/view/']").first
        if await link.count():
            href = urljoin(settings.linkedin_base_url, await link.get_attribute("href") or "")
        title = await _text(card, (
            ".job-card-list__title",
            ".artdeco-entity-lockup__title",
            "a[href*='/jobs/view/']",
        ))
        company = await _text(card, (
            ".artdeco-entity-lockup__subtitle",
            ".job-card-container__company-name",
            "h4",
        ))
        location = await _text(card, (
            ".job-card-container__metadata-item",
            ".artdeco-entity-lockup__caption",
            "[class*='location']",
        ))
        posted = await _text(card, (
            "time",
            "[class*='listed-time']",
            "[class*='posted']",
        ))
        result.append(asdict(JobListing(
            title=title,
            company=company,
            location=location,
            url=href,
            posted=posted,
            text=text,
        )))
    return result
