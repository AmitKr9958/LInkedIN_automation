from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from urllib.parse import quote_plus, urljoin
import json
import logging
import re

from ..job_normalize import normalize_job_url
from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class Job:
    title: str
    company: str = ""
    location: str = ""
    href: str = ""
    posted: str = ""
    posted_hours: float | None = None
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
    "a[href*='/jobs/collections/']",
    "[data-job-id]",
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
    "[data-test-job-posted-date]",
)

EASY_APPLY_SELECTORS = (
    ".job-card-container__apply-method",
    "[class*='apply-method']",
)

DETAIL_COMPANY_SELECTORS = (
    ".job-details-jobs-unified-top-card__company-name a",
    ".job-details-jobs-unified-top-card__company-name",
    ".jobs-unified-top-card__company-name a",
    ".jobs-unified-top-card__company-name",
    ".topcard__org-name-link",
)

DETAIL_POSTED_SELECTORS = (
    ".job-details-jobs-unified-top-card__primary-description-container time",
    ".job-details-jobs-unified-top-card__posted-date",
    ".jobs-unified-top-card__posted-date",
    ".job-details-jobs-unified-top-card__primary-description-container",
)

MAX_DETAIL_HYDRATION = 10

_POSTED_RE = re.compile(
    r"(?i)\b(?:just now|\d+\+?\s+(?:minute|hour|day|week|month|year)s?\s+ago|"
    r"today|yesterday|\d+\+?\s+(?:minute|hour|day|week|month|year)s?\b)"
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
    length = len(value)
    if length >= 4 and length % 2 == 0:
        half = length // 2
        if value[:half] == value[half:]:
            value = value[:half]
    words = value.split()
    if len(words) >= 2 and len(words) % 2 == 0:
        half = len(words) // 2
        if words[:half] == words[half:]:
            value = " ".join(words[:half])
    return value


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _normalize_location_text(value: str) -> str:
    """Normalize punctuation/aliases while preserving words for token matching."""
    normalized = (value or "").lower()
    normalized = normalized.replace("–", "-").replace("—", "-")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = re.sub(r"\bgurugram\b", "gurgaon", normalized)
    normalized = re.sub(r"\bncr\b", "delhi", normalized)
    return normalized


def _location_matches_requested(location: str, requested: str) -> bool:
    """Return whether a LinkedIn result explicitly contains the requested city."""
    requested_token = _normalize_location_text(requested)
    actual = _normalize_location_text(location)
    if not requested_token:
        return True
    if not actual:
        return False
    requested_words = requested_token.split()
    actual_words = set(actual.split())
    if not all(word in actual_words for word in requested_words):
        return False
    return True


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


def _looks_like_posted(value: str) -> bool:
    return bool(_POSTED_RE.search(value))


def _fallback_company(raw_text: str, title: str, location: str, posted: str) -> str:
    if not raw_text or not title:
        return ""
    excluded = {title.lower(), location.lower(), posted.lower(), *_NOISE_LINES}
    noise_fragments = ("alumni work here", "within the past", "applicant")
    noise_lines = {"viewed", "applied", "reposted", "promoted", "sponsored"}
    for line in _lines(raw_text):
        normalized = " ".join(line.split())
        lower = normalized.lower()
        if lower in excluded or _looks_like_location(normalized) or _looks_like_posted(normalized):
            continue
        if any(fragment in lower for fragment in noise_fragments):
            continue
        if "easy apply" in lower or "with verification" in lower:
            continue
        if lower in noise_lines or lower == title.lower():
            continue
        if len(normalized) > 1:
            return normalized
    return ""


async def _logo_company(card) -> str:
    for selector in ("img[alt$=' logo']", "img[alt$=' Logo']"):
        loc = card.locator(selector).first
        try:
            if not await loc.count():
                continue
            alt = ((await loc.get_attribute("alt")) or "").strip()
        except Exception:
            continue
        if "{" in alt:
            continue
        if alt.lower().endswith(" logo"):
            value = alt[:-5].strip()
            if value:
                return value
    return ""


def _clean_company_attr(value: str) -> str:
    value = " ".join(value.split())
    lowered = value.lower()
    for prefix in ("company, ", "company: "):
        if lowered.startswith(prefix):
            value = value[len(prefix):].strip()
            lowered = value.lower()
    if not value or len(value) > 80 or _looks_like_location(value) or _looks_like_posted(value):
        return ""
    return value


async def _company_from_attributes(card) -> str:
    for selector in COMPANY_SELECTORS:
        loc = card.locator(selector).first
        try:
            if not await loc.count():
                continue
        except Exception:
            continue
        value = _clean_company_attr(await _attribute_text(loc))
        if value:
            return value
    return ""


def _normalize_posted(value: str) -> str:
    collapsed = " ".join(value.split())
    if not collapsed:
        return ""
    match = _POSTED_RE.search(collapsed)
    if not match:
        return ""
    found = re.sub(r"(?i)\s+within the past 24 hours$", "", match.group(0).strip()).strip()
    lowered = found.lower()
    if lowered == "just now":
        return "Just now"
    if lowered == "today":
        return "Today"
    if lowered == "yesterday":
        return "Yesterday"
    return found


_UNIT_HOURS = {
    "minute": 1 / 60,
    "hour": 1.0,
    "day": 24.0,
    "week": 24 * 7,
    "month": 24 * 30,
    "year": 24 * 365,
}


def _hours_from_posted(posted: str) -> float | None:
    value = posted.strip().lower()
    if not value:
        return None
    if value in ("just now", "today"):
        return 0.0
    if value == "yesterday":
        return 24.0
    match = re.search(r"(\d+)\+?\s*(minute|hour|day|week|month|year)", value)
    if not match:
        return None
    return round(float(match.group(1)) * _UNIT_HOURS[match.group(2)], 2)


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _relative_from_datetime(value: str) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return ""
    seconds = max((datetime.now(timezone.utc) - parsed).total_seconds(), 0.0)
    if seconds < 60:
        return "Just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = int(seconds // 3600)
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(seconds // 86_400)
    if days < 7:
        return f"{days} day{'s' if days != 1 else ''} ago"
    if days < 30:
        weeks = days // 7
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


def _hours_from_datetime(value: str) -> float | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    seconds = max((datetime.now(timezone.utc) - parsed).total_seconds(), 0.0)
    return round(seconds / 3600, 2)


async def _attribute_text(locator) -> str:
    for attr in ("aria-label", "title", "datetime"):
        try:
            value = await locator.get_attribute(attr)
        except Exception:
            continue
        if value and value.strip():
            return " ".join(value.split())
    return ""


async def _posted(card) -> tuple[str, float | None]:
    value = _normalize_posted(await _text(card, POSTED_SELECTORS))
    if value:
        return value, _hours_from_posted(value)
    for selector in POSTED_SELECTORS:
        loc = card.locator(selector).first
        try:
            if not await loc.count():
                continue
        except Exception:
            continue
        value = _normalize_posted(await _attribute_text(loc))
        if value:
            return value, _hours_from_posted(value)
    try:
        node = card.locator("time[datetime]").first
        if await node.count():
            raw = await node.get_attribute("datetime") or ""
            value = _relative_from_datetime(raw)
            if value:
                return value, _hours_from_datetime(raw)
    except Exception:
        pass
    try:
        text = await card.inner_text()
    except Exception:
        text = ""
    value = _normalize_posted(" ".join(text.split()))
    if value:
        return value, _hours_from_posted(value)
    return "", None


def _walk_nodes(data) -> Iterable[dict]:
    if isinstance(data, dict):
        yield data
        for value in data.values():
            yield from _walk_nodes(value)
    elif isinstance(data, list):
        for item in data:
            yield from _walk_nodes(item)


def _jsonld_job_fields(payloads: Iterable[str]) -> dict:
    fields: dict = {"company": "", "posted": "", "posted_hours": None}
    for payload in payloads:
        try:
            data = json.loads(payload)
        except (TypeError, ValueError):
            continue
        for node in _walk_nodes(data):
            organization = node.get("hiringOrganization")
            company = ""
            if isinstance(organization, dict):
                company = str(organization.get("name") or "").strip()
            elif isinstance(organization, str):
                company = organization.strip()
            if company and not fields["company"]:
                fields["company"] = company
            raw_date = str(node.get("datePosted") or "").strip()
            if raw_date and not fields["posted"]:
                label = _relative_from_datetime(raw_date)
                if label:
                    fields["posted"] = label
                    fields["posted_hours"] = _hours_from_datetime(raw_date)
    return fields


async def _jsonld_texts(page) -> list[str]:
    script = (
        "() => Array.from(document.querySelectorAll("
        "'script[type=\"application/ld+json\"]')).map(e => e.textContent || '')"
    )
    try:
        values = await page.evaluate(script)
    except Exception:
        return []
    return [v for v in (values or []) if isinstance(v, str) and v.strip()]


async def _detail_company_from_links(page) -> str:
    links = page.locator("a[href*='/company/']")
    try:
        total = min(await links.count(), 8)
    except Exception:
        return ""
    for index in range(total):
        link = links.nth(index)
        try:
            text = " ".join(((await link.inner_text()) or "").split())
        except Exception:
            continue
        if text and not text.lower().startswith(("show ", "see ")):
            return text[:80]
    return ""


def _company_from_page_title(title: str) -> str:
    parts = [part.strip() for part in (title or "").split("|")]
    if len(parts) >= 3 and parts[-1].lower() == "linkedin":
        candidate = parts[-2]
        if candidate and candidate.lower() != "linkedin":
            return candidate[:80]
    return ""


async def _main_text(page, limit: int = 2500) -> str:
    text = ""
    try:
        main = page.locator("main").first
        if await main.count():
            text = await main.inner_text()
    except Exception:
        text = ""
    if not text:
        try:
            text = await page.inner_text("body")
        except Exception:
            text = ""
    return " ".join(text.split())[:limit]


async def _detail_fields(page, href: str) -> dict:
    fields: dict = {"company": "", "posted": "", "posted_hours": None}
    try:
        await page.goto(href, wait_until="domcontentloaded")
    except Exception:
        return fields
    try:
        await page.wait_for_timeout(1200)
    except Exception:
        pass

    company = await _text(page, DETAIL_COMPANY_SELECTORS)
    if not company:
        company = await _detail_company_from_links(page)
    if not company:
        company = await _logo_company(page)
    if not company:
        try:
            company = _company_from_page_title(await page.title())
        except Exception:
            company = ""

    posted_hours = None
    posted = _normalize_posted(await _text(page, DETAIL_POSTED_SELECTORS))
    if not posted:
        try:
            node = page.locator("time[datetime]").first
            if await node.count():
                raw = await node.get_attribute("datetime") or ""
                label = _relative_from_datetime(raw)
                if label:
                    posted, posted_hours = label, _hours_from_datetime(raw)
        except Exception:
            pass
    if not posted:
        posted = _normalize_posted(await _main_text(page))
    if posted and posted_hours is None:
        posted_hours = _hours_from_posted(posted)

    fields.update(company=company, posted=posted, posted_hours=posted_hours)
    structured = _jsonld_job_fields(await _jsonld_texts(page))
    if not fields["company"] and structured["company"]:
        fields["company"] = structured["company"]
    if not fields["posted"] and structured["posted"]:
        fields["posted"] = structured["posted"]
        fields["posted_hours"] = structured["posted_hours"]
    return fields


def _merge_detail(job: Job, detail: dict) -> None:
    if not job.company and detail.get("company"):
        job.company = detail["company"]
    if not job.posted and detail.get("posted"):
        job.posted = detail["posted"]
    if job.posted_hours is None and detail.get("posted_hours") is not None:
        job.posted_hours = detail["posted_hours"]


async def _hydrate(page, cards) -> None:
    try:
        total = min(await cards.count(), 50)
    except Exception:
        return
    for index in range(0, total, 5):
        try:
            await cards.nth(index).scroll_into_view_if_needed(timeout=2000)
            await page.wait_for_timeout(150)
        except Exception:
            continue
    try:
        await page.wait_for_timeout(400)
    except Exception:
        pass


async def search(page, keywords: str, location: str = "", start: int = 0) -> list[Job]:
    params = f"keywords={quote_plus(keywords)}"
    if location:
        params += f"&location={quote_plus(location)}"
    if start:
        params += f"&start={start}"

    await page.goto(
        f"{settings.linkedin_base_url}/jobs/search/?{params}",
        wait_until="domcontentloaded",
        timeout=60_000,
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

    await _hydrate(page, cards)

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
        if not company:
            company = await _logo_company(card)
        if not company:
            company = await _company_from_attributes(card)
        location_text = await _text(card, LOCATION_SELECTORS)
        posted, posted_hours = await _posted(card)

        if not company:
            company = _fallback_company(text, title, location_text, posted)

        if not title and not company and not location_text:
            continue

        canonical_href = normalize_job_url(href)
        key = canonical_href.lower()
        if not key:
            key = "|".join(part.strip().lower() for part in (title, company, location_text))
        if key and key in seen:
            continue
        if key:
            seen.add(key)

        if location and not _location_matches_requested(location_text, location):
            continue

        easy_apply = "easy apply" in text.lower()
        if not easy_apply:
            for selector in EASY_APPLY_SELECTORS:
                badge = card.locator(selector)
                try:
                    if await badge.count() and "easy apply" in ((await badge.first.text_content()) or "").lower():
                        easy_apply = True
                        break
                except Exception:
                    continue

        logger.debug(
            "JOB %s card company: %s; card posted: %s",
            canonical_href or title or "<unknown>",
            company or "missing",
            posted or "missing",
        )

        result.append(Job(
            title=title,
            company=company,
            location=location_text,
            href=canonical_href or href,
            posted=posted,
            posted_hours=posted_hours,
            easy_apply=easy_apply,
            text=text,
        ))

    hydrated = 0
    for job in result:
        if hydrated >= MAX_DETAIL_HYDRATION:
            break
        if (job.company and job.posted) or not job.href:
            continue
        card_company = bool(job.company)
        card_posted = bool(job.posted)
        detail = await _detail_fields(page, job.href)
        hydrated += 1
        _merge_detail(job, detail)
        logger.debug(
            "JOB %s card company: %s; card posted: %s; detail company: %s; detail posted: %s; "
            "company source: %s; posted source: %s",
            job.href,
            "found" if card_company else "missing",
            "found" if card_posted else "missing",
            "found" if detail.get("company") else "missing",
            "found" if detail.get("posted") else "missing",
            "card" if card_company else ("detail-page" if job.company else "missing"),
            "card" if card_posted else ("detail-page" if job.posted else "missing"),
        )

    return result
