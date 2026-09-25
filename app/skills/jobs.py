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
from ..job_metadata import extract_application_url, parse_applicant_count, parse_experience

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
    source: str = "linkedin"
    applicant_count: int | None = None
    applicant_count_text: str | None = None
    experience_low: int | None = None
    experience_high: int | None = None
    experience_detected: bool = False
    application_url: str | None = None

    def to_dict(self):
        return asdict(self)


# Prefer selectors that identify an actual job result card on the
# current LinkedIn SDUI layout. Generic scaffold list items can contain
# non-job wrappers and caused live searches to be discarded.
CARD_SELECTORS = (
    "[data-occludable-job-id]",
    ".job-card-container",
    "li:has(a[href*='/jobs/view/'])",
    "[data-job-id]",
    "li.jobs-search-results__list-item",
    "li.scaffold-layout__list-item",
    "li:has(a[href*='/jobs/collections/'])",
    "article:has(a[href*='/jobs/'])",
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

DETAIL_LOCATION_SELECTORS = (
    ".job-details-jobs-unified-top-card__primary-description-container",
    ".jobs-unified-top-card__primary-description-container",
    ".topcard__flavor--bullet-location",
)

DETAIL_TITLE_SELECTORS = (
    ".job-details-jobs-unified-top-card__job-title h1",
    ".job-details-jobs-unified-top-card__job-title",
    ".jobs-unified-top-card__job-title h1",
    ".jobs-unified-top-card__job-title",
    "h1.t-24",
    "h1",
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
    try:
        links = card.locator("a[href*='/jobs/']")
        total = await links.count()
    except Exception:
        total = 0
    for index in range(min(total, 8)):
        try:
            href_value = await links.nth(index).get_attribute("href") or ""
        except Exception:
            continue
        if "/jobs/view/" in href_value or "/jobs/" in href_value:
            return normalize_job_url(urljoin(settings.linkedin_base_url, href_value))
    try:
        raw_href = await card.get_attribute("href") or ""
        if "/jobs/" in raw_href:
            return normalize_job_url(urljoin(settings.linkedin_base_url, raw_href))
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


_DOT_SPLIT = re.compile(r"[\u00b7\u2022]")


def _location_from_detail_text(text: str, title: str = "") -> str:
    """Recover the location from the 2026 detail-page top card.

    The visible top card renders as "{title} {City, State, Country} - {posted} - ..."
    with no dedicated location element, so parse the first dot-separated segment
    and strip the known card title from it.
    """
    if not text:
        return ""
    segment = _DOT_SPLIT.split(text, maxsplit=1)[0].strip()
    if not segment:
        return ""
    if title and segment.lower().startswith(title.lower()):
        segment = segment[len(title):].strip()
    if not segment:
        return ""
    lower = segment.lower()
    if "," not in segment and not any(
        token in lower for token in ("remote", "hybrid", "on-site")
    ):
        return ""
    if title and _looks_like_location(segment):
        return segment
    comma = segment.find(",")
    if comma < 1:
        return segment if _looks_like_location(segment) else ""
    start = segment.rfind(" ", 0, comma)
    candidate = segment[start + 1 if start >= 0 else 0:].strip()
    return candidate if _looks_like_location(candidate) else ""


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


async def _location(card, raw_text: str) -> str:
    value = await _text(card, LOCATION_SELECTORS)
    if value and _looks_like_location(value):
        return value
    # Current SDUI cards sometimes expose location as plain text rather than
    # a dedicated metadata element. Recover it from visible card lines.
    for line in _lines(raw_text):
        if _looks_like_location(line):
            return line
    return value


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
    fields: dict = {"title": "", "company": "", "posted": "", "posted_hours": None, "location": "", "applicant_count": None, "applicant_count_text": None, "experience_low": None, "experience_high": None, "experience_detected": False, "application_url": None}
    for payload in payloads:
        try:
            data = json.loads(payload)
        except (TypeError, ValueError):
            continue
        for node in _walk_nodes(data):
            title = str(node.get("title") or node.get("name") or "").strip()
            if title and not fields["title"]:
                fields["title"] = title
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
            raw_location = node.get("jobLocation")
            location = ""
            if isinstance(raw_location, dict):
                address = raw_location.get("address")
                if isinstance(address, dict):
                    parts = [
                        str(address.get(key) or "").strip()
                        for key in ("addressLocality", "addressRegion", "addressCountry")
                    ]
                    location = ", ".join(part for part in parts if part)
                elif isinstance(address, str):
                    location = address.strip()
            elif isinstance(raw_location, str):
                location = raw_location.strip()
            if location and not fields["location"]:
                fields["location"] = location
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


async def _detail_fields(page, href: str, title: str = "") -> dict:
    fields: dict = {"title": "", "company": "", "posted": "", "posted_hours": None, "location": ""}
    try:
        await page.goto(href, wait_until="domcontentloaded")
    except Exception:
        return fields
    try:
        await page.wait_for_timeout(1200)
    except Exception:
        pass

    detail_title = _clean_title(await _text(page, DETAIL_TITLE_SELECTORS))
    if not detail_title:
        try:
            page_title = await page.title()
            # LinkedIn titles often look like "Job Title | Company | LinkedIn"
            detail_title = _clean_title(page_title.split("|")[0].strip()) if page_title else ""
        except Exception:
            detail_title = ""
    fields["title"] = detail_title

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
    main_text = await _main_text(page)
    applicant = parse_applicant_count(main_text)
    fields["applicant_count"], fields["applicant_count_text"] = applicant.count, applicant.text
    experience = parse_experience(main_text, fields.get("title") or title)
    fields["experience_low"], fields["experience_high"], fields["experience_detected"] = experience.low, experience.high, experience.detected
    try:
        links = await page.locator("a[href]").evaluate_all("(els) => els.map(e => ({href:e.href, text:e.innerText || '', aria:e.getAttribute('aria-label') || '', title:e.getAttribute('title') || ''}))")
    except Exception:
        links = []
    fields["application_url"] = extract_application_url(main_text, links)
    if not posted:
        posted = _normalize_posted(main_text)
    if posted and posted_hours is None:
        posted_hours = _hours_from_posted(posted)

    location = _location_from_detail_text(await _text(page, DETAIL_LOCATION_SELECTORS), title)
    if not location:
        location = _location_from_detail_text(main_text, title)

    fields.update(company=company, posted=posted, posted_hours=posted_hours, location=location)
    structured = _jsonld_job_fields(await _jsonld_texts(page))
    if not fields["title"] and structured.get("title"):
        fields["title"] = _clean_title(structured["title"])
    if not fields["company"] and structured["company"]:
        fields["company"] = structured["company"]
    if not fields["posted"] and structured["posted"]:
        fields["posted"] = structured["posted"]
        fields["posted_hours"] = structured["posted_hours"]
    if not fields["location"] and structured["location"]:
        fields["location"] = structured["location"]
    return fields


def _merge_detail(job: Job, detail: dict) -> None:
    if not job.title and detail.get("title"):
        job.title = detail["title"]
    if not job.company and detail.get("company"):
        job.company = detail["company"]
    if not job.posted and detail.get("posted"):
        job.posted = detail["posted"]
    if job.posted_hours is None and detail.get("posted_hours") is not None:
        job.posted_hours = detail["posted_hours"]
    if not job.location and detail.get("location"):
        job.location = detail["location"]
    if job.applicant_count is None and detail.get("applicant_count") is not None:
        job.applicant_count = detail["applicant_count"]
        job.applicant_count_text = detail.get("applicant_count_text")
    if not job.experience_detected and detail.get("experience_detected"):
        job.experience_low = detail.get("experience_low")
        job.experience_high = detail.get("experience_high")
        job.experience_detected = True
    if not job.application_url and detail.get("application_url"):
        job.application_url = detail["application_url"]


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


def _bump(diagnostics: dict | None, key: str) -> None:
    """Increment a safe pipeline-stage counter (no URLs or session data)."""
    if diagnostics is not None:
        diagnostics[key] = diagnostics.get(key, 0) + 1


async def search(
    page,
    keywords: str,
    location: str = "",
    start: int = 0,
    diagnostics: dict | None = None,
) -> list[Job]:
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

    # SDUI job results render client-side after domcontentloaded; wait for
    # the first card of any known shape before counting so a slow render is
    # not mistaken for an empty result set.
    try:
        await page.wait_for_selector(
            ", ".join((*CARD_SELECTORS, "main a[href*='/jobs/']")),
            timeout=12_000,
        )
    except Exception:
        pass

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
        # Fallback for newer LinkedIn SDUI layouts where the card container
        # itself no longer carries a stable class.
        link_cards = page.locator("main a[href*='/jobs/']")
        if await link_cards.count():
            cards = link_cards
        else:
            if diagnostics is not None:
                diagnostics["cards_detected"] = 0
                diagnostics["returned"] = 0
            return []

    try:
        await cards.first.wait_for(state="visible", timeout=10_000)
    except Exception:
        pass

    await _hydrate(page, cards)

    parsed: list[Job] = []
    seen: set[str] = set()

    for i in range(min(await cards.count(), 50)):
        card = cards.nth(i)
        _bump(diagnostics, "cards_detected")
        try:
            text = " ".join((await card.inner_text()).split())
        except Exception:
            continue

        href = await _href(card)
        if not href:
            try:
                raw_href = await card.get_attribute("href")
            except Exception:
                raw_href = ""
            if raw_href and "/jobs/" in raw_href:
                href = normalize_job_url(urljoin(settings.linkedin_base_url, raw_href))
        if href:
            _bump(diagnostics, "urls_extracted")
        title = _clean_title(await _text(card, TITLE_SELECTORS))
        if not title and href:
            try:
                title = _clean_title(await card.inner_text())
            except Exception:
                title = ""
        if title:
            _bump(diagnostics, "titles_extracted")
        company = await _text(card, COMPANY_SELECTORS)
        if not company:
            company = await _logo_company(card)
        if not company:
            company = await _company_from_attributes(card)
        location_text = await _location(card, text)
        if location_text:
            _bump(diagnostics, "locations_extracted")
        posted, posted_hours = await _posted(card)
        if posted:
            _bump(diagnostics, "posted_extracted")
        applicant = parse_applicant_count(text)
        experience = parse_experience(text, title)
        try:
            card_links = await card.locator("a[href]").evaluate_all("(els) => els.map(e => ({href:e.href, text:e.innerText || '', aria:e.getAttribute('aria-label') || '', title:e.getAttribute('title') || ''}))")
        except Exception:
            card_links = []
        application_url = extract_application_url(card_links)
        if applicant.count is not None:
            _bump(diagnostics, "applicant_count_extracted")
        if experience.detected:
            _bump(diagnostics, "experience_detected")

        if not company:
            company = _fallback_company(text, title, location_text, posted)
        if company:
            _bump(diagnostics, "companies_extracted")

        if not title and not company and not location_text:
            _bump(diagnostics, "rejected_empty")
            continue

        canonical_href = normalize_job_url(href)
        key = canonical_href.lower()
        if not key:
            key = "|".join(part.strip().lower() for part in (title, company, location_text))
        if key and key in seen:
            _bump(diagnostics, "rejected_duplicate")
            continue
        if key:
            seen.add(key)

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

        parsed.append(Job(
            title=title,
            company=company,
            location=location_text,
            href=canonical_href or href,
            posted=posted,
            posted_hours=posted_hours,
            easy_apply=easy_apply,
            text=text,
            source="linkedin",
            applicant_count=applicant.count,
            applicant_count_text=applicant.text,
            experience_low=experience.low,
            experience_high=experience.high,
            experience_detected=experience.detected,
            application_url=application_url,
        ))

    hydrated = 0
    for job in parsed:
        if hydrated >= MAX_DETAIL_HYDRATION:
            break
        # Visit detail when any required field is missing (title/company/posted/location).
        needs_detail = not (job.title and job.company and job.posted and job.location)
        if not needs_detail or not job.href:
            continue
        card_title = bool(job.title)
        card_company = bool(job.company)
        card_posted = bool(job.posted)
        card_location = bool(job.location)
        detail = await _detail_fields(page, job.href, title=job.title)
        hydrated += 1
        _bump(diagnostics, "detail_pages_visited")
        _merge_detail(job, detail)
        if job.title and not card_title:
            _bump(diagnostics, "title_filled_from_detail")
        if job.company and not card_company:
            _bump(diagnostics, "company_filled_from_detail")
        if job.posted and not card_posted:
            _bump(diagnostics, "posted_filled_from_detail")
        if job.location and not card_location:
            _bump(diagnostics, "location_filled_from_detail")
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

    # Apply the requested-location rule only after detail hydration so cards
    # whose location is not rendered on the list page can still qualify.
    # Reject incomplete records: a production Job must have at least a title
    # and a usable href (company/location are strongly preferred but title+href
    # are the minimum contract for downstream ranking/tracking).
    result: list[Job] = []
    for job in parsed:
        if not job.title or not job.href:
            _bump(diagnostics, "rejected_incomplete")
            continue
        if location and not _location_matches_requested(job.location, location):
            _bump(diagnostics, "rejected_location")
            continue
        if job.applicant_count is not None:
            _bump(diagnostics, "applicant_count_known")
        else:
            _bump(diagnostics, "applicant_count_unknown")
        if job.experience_detected:
            _bump(diagnostics, "experience_detected_final")
        else:
            _bump(diagnostics, "experience_unknown")
        result.append(job)

    if diagnostics is not None:
        diagnostics["returned"] = len(result)
        diagnostics["returned_after_location"] = len(result)
    return result
