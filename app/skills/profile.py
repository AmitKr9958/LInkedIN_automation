from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import re

from ..linkedin_reader import current_session_state
from ..config import settings


@dataclass
class ProfileSnapshot:
    authenticated: bool
    url: str
    title: str
    name: str = ""
    headline: str = ""
    location: str = ""
    about: str = ""
    experience: str = ""
    skills: str = ""
    featured: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PROFILE_NAME_SELECTORS = (
    "main h1",
    "h1.text-heading-xlarge",
    "h1",
)

PROFILE_HEADLINE_SELECTORS = (
    "div.pv-text-details__left-panel .text-body-medium.break-words",
    "div.pv-text-details__left-panel .text-body-medium",
    "main .text-body-medium.break-words",
    "main .text-body-medium",
    "[data-generated-suggestion-target*='headline']",
    "[class*='headline']",
)

PROFILE_LOCATION_SELECTORS = (
    "div.pv-text-details__left-panel .text-body-small.inline",
    "div.pv-text-details__left-panel .text-body-small.break-words",
    "div.pv-text-details__left-panel .text-body-small",
    "main .text-body-small.inline",
    "main .text-body-small",
    "[data-generated-suggestion-target*='location']",
    "[class*='location']",
    "[class*='text-body-small']",
)

_LOCATION_RE = re.compile(
    r"(?i)\b(?:india|delhi|new delhi|gurgaon|gurugram|noida|jaipur|"
    r"mumbai|bengaluru|bangalore|hyderabad|pune|chennai|kolkata)\b"
)

_PROFILE_NOISE = {
    "1st",
    "2nd",
    "3rd",
    "contact info",
    "followers",
    "connections",
    "open to work",
    "more",
    "message",
    "connect",
    "he/him",
    "she/her",
    "they/them",
    "he him",
    "she her",
    "they them",
}


def _is_valid_headline(text: str, known_name: str = "") -> bool:
    normalized = " ".join((text or "").split())
    if not normalized or normalized.lower() in _PROFILE_NOISE:
        return False
    if known_name and normalized.lower() == known_name.strip().lower():
        return False
    return re.fullmatch(r"(?i)(he|she|they)(?:[/ ](?:him|her|them))?", normalized) is None


async def read_profile(page) -> ProfileSnapshot:
    profile_url = str(settings.profile_url or "").strip()
    if not re.match(r"^https://(?:www\.)?linkedin\.com/in/[^/?#]+/?(?:\?.*)?$", profile_url, re.I):
        raise RuntimeError(
            "PROFILE_URL must point to the authenticated LinkedIn profile, "
            "for example https://www.linkedin.com/in/your-profile-slug/"
        )

    await page.goto(profile_url, wait_until="domcontentloaded", timeout=60_000)
    await page.wait_for_timeout(2_500)
    # LinkedIn lazy-loads profile sections while scrolling. The headed browser
    # may not visibly show a scrollbar, so force a full programmatic scroll.
    await _scroll_profile_to_bottom(page)
    state = await current_session_state(page)

    name_locator = page.locator("main h1, h1.text-heading-xlarge, h1").first
    try:
        await name_locator.wait_for(state="visible", timeout=10_000)
    except Exception:
        pass

    name = await _first_text(page, PROFILE_NAME_SELECTORS)
    headline = await _first_valid_text(page, PROFILE_HEADLINE_SELECTORS, name)
    location = await _first_valid_text(page, PROFILE_LOCATION_SELECTORS, name)

    top_text = await _top_card_text(page)
    if not name:
        name = _name_from_title(state["title"])
    if not headline or not location:
        fallback_name, fallback_headline, fallback_location = _parse_top_card(
            top_text, name
        )
        name = name or fallback_name
        headline = headline or fallback_headline
        location = location or fallback_location

    sections = {
        "about": await _read_profile_section(page, "about"),
        "experience": await _read_profile_section(page, "experience"),
        "skills": await _read_profile_section(page, "skills"),
        "featured": await _read_profile_section(page, "featured"),
    }

    return ProfileSnapshot(
        state["authenticated"],
        state["url"],
        state["title"],
        name,
        headline,
        location,
        sections["about"],
        sections["experience"],
        sections["skills"],
        sections["featured"],
    )


async def _scroll_profile_to_bottom(page, max_rounds: int = 24) -> None:
    last_height = 0
    stable_rounds = 0
    for _ in range(max_rounds):
        try:
            height = await page.evaluate("document.scrollingElement ? document.scrollingElement.scrollHeight : document.body.scrollHeight")
            viewport = await page.evaluate("window.innerHeight || document.documentElement.clientHeight || 0")
            await page.evaluate("window.scrollBy(0, Math.max(600, Math.floor(window.innerHeight * 0.8)))")
            await page.wait_for_timeout(450)
            new_height = await page.evaluate("document.scrollingElement ? document.scrollingElement.scrollHeight : document.body.scrollHeight")
            if new_height <= height and new_height <= last_height:
                stable_rounds += 1
            else:
                stable_rounds = 0
            last_height = max(last_height, new_height)
            scroll_y = await page.evaluate("window.scrollY || window.pageYOffset || 0")
            if viewport and scroll_y + viewport >= new_height - 8 and stable_rounds >= 2:
                break
            if stable_rounds >= 4:
                break
        except Exception:
            break

    try:
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(250)
    except Exception:
        pass


async def _first_text(page, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        loc = page.locator(selector)
        try:
            if await loc.count():
                text = await loc.first.text_content()
                if text and text.strip():
                    return " ".join(text.split())
        except Exception:
            continue
    return ""


async def _first_valid_text(page, selectors: tuple[str, ...], known_name: str = "") -> str:
    for selector in selectors:
        loc = page.locator(selector)
        try:
            count = await loc.count()
            for index in range(min(count, 10)):
                text = " ".join((await loc.nth(index).text_content() or "").split())
                if _is_valid_headline(text, known_name):
                    return text
        except Exception:
            continue
    return ""


async def _read_profile_section(page, section_name: str) -> str:
    title = section_name.strip().lower()

    # Prefer semantic section headings over LinkedIn's frequently changing
    # generated IDs/classes. The returned text is read-only DOM content.
    try:
        value = await page.evaluate(
            """(wanted) => {
                const norm = value => (value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                const headings = Array.from(document.querySelectorAll('main h2, main h3'));
                const heading = headings.find(h => norm(h.textContent) === wanted);
                if (!heading) return '';
                const section = heading.closest('section') || heading.parentElement;
                return section ? (section.innerText || '') : '';
            }""",
            title,
        )
        value = " ".join(str(value or "").split())
        if value:
            return value
    except Exception:
        pass

    # Fallbacks for older LinkedIn markup.
    selectors = (
        f"section#{section_name}",
        f"div#{section_name}",
        f"[data-section='{section_name}']",
        f"[data-section-id='{section_name}']",
    )
    for selector in selectors:
        loc = page.locator(selector).first
        try:
            if await loc.count():
                text = " ".join((await loc.inner_text()).split())
                if text:
                    return text
        except Exception:
            continue
    return ""


async def _top_card_text(page) -> str:
    for selector in (
        "main",
        "section[data-member-id]",
        "main section",
    ):
        loc = page.locator(selector).first
        try:
            if await loc.count():
                text = await loc.inner_text()
                if text and text.strip():
                    return text
        except Exception:
            continue
    return ""


def _parse_top_card(raw_text: str, known_name: str) -> tuple[str, str, str]:
    lines = [" ".join(x.split()) for x in raw_text.splitlines() if x.strip()]
    lines = [x for x in lines if x.lower() not in _PROFILE_NOISE]

    name = known_name.strip()
    if not name:
        for line in lines[:15]:
            if 2 <= len(line.split()) <= 5 and not _LOCATION_RE.search(line):
                name = line
                break

    name_index = next(
        (i for i, line in enumerate(lines) if line.lower() == name.lower()),
        -1,
    )

    candidates = lines[name_index + 1 :] if name_index >= 0 else lines[:20]
    headline = ""
    location = ""

    for line in candidates[:20]:
        lower = line.lower()
        if lower == name.lower() or lower in _PROFILE_NOISE:
            continue
        if _LOCATION_RE.search(line):
            location = line
            continue
        if not headline and 2 <= len(line) <= 180:
            if not re.search(r"\b(followers?|connections?|experience|education)\b", lower):
                if _is_valid_headline(line, name):
                    headline = line
        if headline and location:
            break

    return name, headline, location


def _name_from_title(title: str) -> str:
    suffix = " | LinkedIn"
    if title.endswith(suffix):
        candidate = title[: -len(suffix)].strip()
        if candidate and candidate.lower() not in {"linkedin", "feed"}:
            return candidate
    return ""
