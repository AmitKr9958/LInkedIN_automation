from __future__ import annotations

from dataclasses import dataclass, asdict
from urllib.parse import quote_plus, urljoin

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
            return urljoin(settings.linkedin_base_url, await link.get_attribute("href") or "")
    except Exception:
        pass
    return ""


def _clean_title(value: str) -> str:
    value = " ".join(value.split())
    # LinkedIn sometimes exposes verification text alongside the title.
    for marker in (" with verification", " with verification "):
        if marker in value.lower():
            index = value.lower().find(marker)
            value = value[:index].strip()
    # Some rendered cards contain the same title twice.
    compact = value.replace(" ", "")
    if len(compact) >= 2 and len(compact) % 2 == 0:
        half = len(compact) // 2
        if compact[:half] == compact[half:]:
            # Preserve the readable first half when LinkedIn renders a
            # title twice without a separator.
            midpoint = len(value) // 2
            left = value[:midpoint].strip()
            right = value[midpoint:].strip()
            if left.replace(" ", "") == right.replace(" ", ""):
                value = left
    words = value.split()
    if len(words) >= 2 and len(words) % 2 == 0:
        half = len(words) // 2
        if words[:half] == words[half:]:
            value = " ".join(words[:half])
    return value


async def _posted(card) -> str:
    value = await _text(card, POSTED_SELECTORS)
    if value:
        return value
    # Footer text is a useful fallback when LinkedIn changes the inner span.
    text = " ".join((await card.inner_text()).split())
    lowered = text.lower()
    for marker in (" ago", "today", "yesterday", "hour", "day", "week", "month"):
        idx = lowered.find(marker)
        if idx >= 0:
            start = max(0, idx - 30)
            candidate = text[start: idx + len(marker)].strip(" ·|-")
            if candidate:
                return candidate
    return ""


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

    # Use one card selector at a time. A comma-separated union of nested
    # selectors returns the same LinkedIn card multiple times.
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
        # Deduplicate by canonical job URL first, then by meaningful content.
        key = href.split("?", 1)[0].rstrip("/").lower()
        title = _clean_title(await _text(card, TITLE_SELECTORS))
        company = await _text(card, COMPANY_SELECTORS)
        location_text = await _text(card, LOCATION_SELECTORS)
        posted = await _posted(card)

        if key and key in seen:
            continue
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
                href=href,
                posted=posted,
                easy_apply=easy_apply,
                text=text,
            )
        )

    return result
