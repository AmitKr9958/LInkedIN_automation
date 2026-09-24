from dataclasses import dataclass, asdict
from typing import Any
from urllib.parse import urljoin
import re

from playwright.async_api import Page

from .linkedin_selectors import AUTHENTICATED_MARKERS, JOB_CARD_SELECTORS, LOGIN_MARKERS
from .config import settings
from .job_normalize import normalize_job_url


@dataclass
class JobListing:
    title: str = ""
    company: str = ""
    location: str = ""
    url: str = ""
    posted: str = ""
    text: str = ""


_POSTED_RE = re.compile(
    r"(?i)\b(?:just now|\d+\s+(?:minute|hour|day|week|month)s?\s+ago|"
    r"today|yesterday|\d+\s+(?:minute|hour|day|week|month)s?\b)"
    r"(?:\s+within the past 24 hours)?"
)


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


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _looks_like_location(value: str) -> bool:
    lower = value.lower()
    return (
        "," in value
        or "(remote)" in lower
        or "remote" in lower
        or "on-site" in lower
        or "hybrid" in lower
        or any(token in lower for token in ("india", "delhi", "gurgaon", "gurugram", "noida", "jaipur"))
    )


def _fallback_company(raw_text: str, title: str, location: str, posted: str) -> str:
    excluded = {title.lower(), location.lower(), posted.lower(), "promoted", "sponsored", "easy apply"}
    for line in _lines(raw_text):
        value = " ".join(line.split())
        lower = value.lower()
        if lower in excluded or lower == title.lower():
            continue
        if _looks_like_location(value) or _POSTED_RE.search(value):
            continue
        if "with verification" in lower:
            continue
        return value
    return ""


async def read_job_cards(page: Page) -> list[dict[str, Any]]:
    cards = None
    for selector in JOB_CARD_SELECTORS:
        candidate = page.locator(selector)
        try:
            if await candidate.count():
                cards = candidate
                break
        except Exception:
            continue

    if cards is None:
        return []

    try:
        await cards.first.wait_for(state="visible", timeout=10_000)
    except Exception:
        pass

    result: list[dict[str, Any]] = []
    seen: set[str] = set()

    for i in range(min(await cards.count(), 50)):
        card = cards.nth(i)
        try:
            raw_text = await card.inner_text()
            text = " ".join(raw_text.split())
        except Exception:
            continue

        href = ""
        link = card.locator("a[href*='/jobs/view/']").first
        try:
            if await link.count():
                href = normalize_job_url(
                    urljoin(settings.linkedin_base_url, await link.get_attribute("href") or "")
                )
        except Exception:
            pass

        title = await _text(
            card,
            (
                ".job-card-list__title",
                ".job-card-list__title-line a",
                ".artdeco-entity-lockup__title a",
                ".artdeco-entity-lockup__title",
                "a[href*='/jobs/view/']",
            ),
        )
        company = await _text(
            card,
            (
                ".job-card-container__primary-description",
                ".job-card-container__company-name",
                ".artdeco-entity-lockup__subtitle a",
                ".artdeco-entity-lockup__subtitle",
                "a[href*='/company/']",
                "h4",
            ),
        )
        location = await _text(
            card,
            (
                ".job-card-container__metadata-item",
                ".job-card-container__metadata-wrapper li",
                ".artdeco-entity-lockup__caption",
                "[class*='location']",
            ),
        )
        posted_value = await _text(
            card,
            (
                "time",
                ".job-card-container__footer-item",
                ".job-card-container__listed-time",
                "[class*='listed-time']",
                "[class*='posted']",
            ),
        )
        posted_match = _POSTED_RE.search(posted_value or text)
        posted = posted_match.group(0).strip() if posted_match else posted_value

        if not company:
            company = _fallback_company(raw_text, title, location, posted)

        key = href.lower().rstrip("/")
        if not key:
            key = "|".join(value.strip().lower() for value in (title, company, location))
        if key and key in seen:
            continue
        if key:
            seen.add(key)

        result.append(
            asdict(
                JobListing(
                    title=title,
                    company=company,
                    location=location,
                    url=href,
                    posted=posted,
                    text=text,
                )
            )
        )

    return result
