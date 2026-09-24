from __future__ import annotations

from dataclasses import dataclass, asdict
from urllib.parse import quote_plus, urljoin
import re

from ..job_normalize import normalize_job_url
from ..config import settings


@dataclass
class Job:
    title: str
    company: str = ""
    location: str = ""
    href: str = ""
    posted: str = ""
    easy_apply: bool = False
    text: str = ""

    def to_dict(self):
        return asdict(self)


CARD_SELECTORS = (
    "li.jobs-search-results__list-item",
    "li.scaffold-layout__list-item",
    "[data-occludable-job-id]",
    ".job-card-container",
)

TITLE_SELECTORS = (
    ".job-card-list__title",
    ".job-card-list__title-line a",
    ".job-card-container__link.job-card-list__title",
    ".artdeco-entity-lockup__title a",
    ".artdeco-entity-lockup__title",
    "a[href*='/jobs/view/']",
)

COMPANY_SELECTORS = (
    ".job-card-container__primary-description",
    ".job-card-container__company-name",
    ".artdeco-entity-lockup__subtitle a",
    ".artdeco-entity-lockup__subtitle",
    "a[href*='/company/']",
    "h4",
)

LOCATION_SELECTORS = (
    ".job-card-container__metadata-item",
    ".job-card-container__metadata-wrapper li",
    ".artdeco-entity-lockup__caption",
    "[class*='location']",
)

POSTED_SELECTORS = (
    "time",
    ".job-card-container__footer-item",
    ".job-card-container__listed-time",
    "[class*='listed-time']",
    "[class*='posted']",
)

EASY_APPLY_SELECTORS = (
    ".job-card-container__apply-method",
    "[class*='apply-method']",
)

_POSTED_RE = re.compile(
    r"(?i)\b(?:just now|\d+\s+(?:minute|hour|day|week|month)s?\s+ago|"
    r"today|yesterday|\d+\s+(?:minute|hour|day|week|month)s?\b)"
    r"(?:\s+within the past 24 hours)?"
)

_NOISE_LINES = {
    "promoted",
    "sponsored",
    "easy apply",
    "with verification",
}


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


async def _href(card) -> str:
    link = card.locator("a[href*='/jobs/view/']").first
    try:
        if await link.count():
            href = urljoin(settings.linkedin_base_url, await link.get_attribute("href") or "")
            return normalize_job_url(href)
    except Exception:
        pass
    return ""


def _clean_title(value: str) -> str:
    value = " ".join(value.split())
    for marker in (" with verification",):
        index = value.lower().find(marker)
        if index >= 0:
            value = value[:index].strip()

    words = value.split()
    if len(words) >= 2 and len(words) % 2 == 0:
        half = len(words) // 2
        if words[:half] == words[half:]:
            value = " ".join(words[:half])
    return value


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
        or any(
            token in lower
            for token in ("india", "delhi", "gurgaon", "gurugram", "noida", "jaipur")
        )
    )


def _looks_like_posted(value: str) -> bool:
    return bool(_POSTED_RE.search(value))


def _fallback_company(raw_text: str, title: str, location: str, posted: str) -> str:
    if not raw_text or not title:
        return ""
    excluded = {title.lower(), location.lower(), posted.lower(), *_NOISE_LINES}
    for line in _lines(raw_text):
        normalized = " ".join(line.split())
        lower = normalized.lower()
        if lower in excluded or _looks_like_location(normalized) or _looks_like_posted(normalized):
            continue
        if "easy apply" in lower or "with verification" in lower:
            continue
        # Search cards often render title twice; skip another exact title.
        if lower == title.lower():
            continue
        if len(normalized) > 1:
            return normalized
    return ""


async def _posted(card) -> str:
    # LinkedIn sometimes renders the relative posting time only in an
    # aria-label/title/datetime attribute, not in the visible card text.
    try:
        await card.scroll_into_view_if_needed(timeout=2_000)
    except Exception:
        pass

    for selector in POSTED_SELECTORS:
        value = await _text(card, (selector,))
        if value and value.strip().lower() not in {"promoted", "sponsored"}:
            match = _POSTED_RE.search(value)
            if match:
                return match.group(0).strip()

    metadata = card.locator("[aria-label], [title], time[datetime]")
    try:
        for i in range(min(await metadata.count(), 100)):
            node = metadata.nth(i)
            candidates = (
                await node.get_attribute("aria-label") or "",
                await node.get_attribute("title") or "",
                await node.get_attribute("datetime") or "",
                (await node.text_content()) or "",
            )
            for candidate in candidates:
                match = _POSTED_RE.search(" ".join(candidate.split()))
                if match:
                    return match.group(0).strip()
    except Exception:
        pass

    try:
        text = await card.inner_text()
    except Exception:
        text = ""
    match = _POSTED_RE.search(" ".join(text.split()))
    return match.group(0).strip() if match else ""


async def search(page, keywords: str, location: str = "", start: int = 0) -> list[Job]:
    params = f"keywords={quote_plus(keywords)}"
    if location:
        params += f"&location={quote_plus(location)}"
    if start:
        params += f"&start={start}"

    await page.goto(
        f"{settings.linkedin_base_url}/jobs/search/?{params}",
        wait_until="domcontentloaded",
    )

    cards = None
    for selector in CARD_SELECTORS:
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

    result: list[Job] = []
    seen: set[str] = set()

    for i in range(min(await cards.count(), 50)):
        card = cards.nth(i)
        try:
            text = " ".join((await card.inner_text()).split())
        except Exception:
            continue

        href = await _href(card)
        title = _clean_title(await _text(card, TITLE_SELECTORS))
        company = await _text(card, COMPANY_SELECTORS)
        location_text = await _text(card, LOCATION_SELECTORS)
        posted = await _posted(card)

        if not company:
            company = _fallback_company(text, title, location_text, posted)

        canonical_href = normalize_job_url(href)
        key = canonical_href.lower()
        if not key:
            key = "|".join(
                part.strip().lower() for part in (title, company, location_text)
            )
        if key and key in seen:
            continue
        if key:
            seen.add(key)

        easy_apply = "easy apply" in text.lower()
        if not easy_apply:
            for selector in EASY_APPLY_SELECTORS:
                badge = card.locator(selector)
                try:
                    if await badge.count() and "easy apply" in (
                        (await badge.first.text_content()) or ""
                    ).lower():
                        easy_apply = True
                        break
                except Exception:
                    continue

        result.append(
            Job(
                title=title,
                company=company,
                location=location_text,
                href=canonical_href or href,
                posted=posted,
                easy_apply=easy_apply,
                text=text,
            )
        )

    return result
