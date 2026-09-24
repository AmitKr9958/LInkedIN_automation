from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

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
    "div.pv-text-details__left-panel .text-body-medium",
    "div.pv-text-details__left-panel .text-body-medium.break-words",
    "main .text-body-medium.break-words",
    "main .text-body-medium",
    "[class*='headline']",
)

PROFILE_LOCATION_SELECTORS = (
    "div.pv-text-details__left-panel .text-body-small.inline",
    "div.pv-text-details__left-panel .text-body-small",
    "main .text-body-small.inline",
    "main .text-body-small",
    "[class*='location']",
)


async def read_profile(page) -> ProfileSnapshot:
    await page.goto(f"{settings.linkedin_base_url}/in/", wait_until="domcontentloaded")
    state = await current_session_state(page)

    # Profile content is client-rendered. Prefer locator-based waiting over a
    # fixed sleep so this remains deterministic across fast/slow machines.
    name_locator = page.locator("main h1, h1.text-heading-xlarge, h1").first
    try:
        await name_locator.wait_for(state="visible", timeout=10_000)
    except Exception:
        pass

    name = await _first_text(page, PROFILE_NAME_SELECTORS)
    headline = await _first_text(page, PROFILE_HEADLINE_SELECTORS)
    location = await _first_text(page, PROFILE_LOCATION_SELECTORS)

    # The profile title is a safe last-resort name source when LinkedIn has
    # rendered the authenticated profile title but not the h1 yet.
    if not name:
        name = _name_from_title(state["title"])

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


def _name_from_title(title: str) -> str:
    suffix = " | LinkedIn"
    if title.endswith(suffix):
        candidate = title[: -len(suffix)].strip()
        if candidate and candidate.lower() not in {"linkedin", "feed"}:
            return candidate
    return ""
