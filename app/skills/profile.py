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
    "[class*='text-body-medium']",
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
}


async def read_profile(page) -> ProfileSnapshot:
    await page.goto(f"{settings.linkedin_base_url}/in/", wait_until="domcontentloaded")
    state = await current_session_state(page)

    name_locator = page.locator("main h1, h1.text-heading-xlarge, h1").first
    try:
        await name_locator.wait_for(state="visible", timeout=10_000)
    except Exception:
        pass

    name = await _first_text(page, PROFILE_NAME_SELECTORS)
    headline = await _first_text(page, PROFILE_HEADLINE_SELECTORS)
    location = await _first_text(page, PROFILE_LOCATION_SELECTORS)

    # LinkedIn changes profile markup frequently. Use the rendered top-card text
    # as a semantic fallback instead of depending on one CSS class family.
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

    return ProfileSnapshot(
        state["authenticated"],
        state["url"],
        state["title"],
        name,
        headline,
        location,
    )


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
            # Skip obvious navigation/metric lines.
            if not re.search(r"\b(followers?|connections?|experience|education)\b", lower):
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
