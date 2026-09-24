from dataclasses import dataclass, asdict
from typing import Any
from urllib.parse import urljoin

from playwright.async_api import Page

from .linkedin_selectors import FEED_MARKERS, JOB_CARD_SELECTORS, LOGIN_MARKERS, PROFILE_MARKERS
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
        locator = page.locator(selector).first
        try:
            if await locator.count() and await locator.is_visible():
                return True
        except Exception:
            continue
    return False

async def current_session_state(page: Page) -> dict[str, Any]:
    url = page.url
    title = await page.title()
    on_login = "/login" in url.lower() or await _visible(page, LOGIN_MARKERS)
    if on_login:
        authenticated = False
        confidence = "high"
    else:
        logged_in_marker = await _visible(page, FEED_MARKERS) or await _visible(page, PROFILE_MARKERS)
        authenticated = bool(logged_in_marker)
        confidence = "medium" if authenticated else "low"
    return {"url": url, "title": title, "authenticated": authenticated, "confidence": confidence}

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
        title = ""
        for sel in ("a[href*='/jobs/view/']", ".job-card-list__title", ".artdeco-entity-lockup__title"):
            loc = card.locator(sel).first
            if await loc.count():
                title = " ".join(((await loc.text_content()) or "").split())
                if title:
                    break
        result.append(asdict(JobListing(title=title, url=href, text=text)))
    return result
