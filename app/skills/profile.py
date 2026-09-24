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

async def read_profile(page) -> ProfileSnapshot:
    await page.goto(f"{settings.linkedin_base_url}/in/", wait_until="domcontentloaded")
    state = await current_session_state(page)
    name = await _first_text(page, ["h1", "main h1"])
    headline = await _first_text(page, ["main .text-body-medium", "[class*='headline']"])
    location = await _first_text(page, ["main .text-body-small", "[class*='location']"])
    return ProfileSnapshot(state["authenticated"], state["url"], state["title"], name, headline, location)

async def _first_text(page, selectors: list[str]) -> str:
    for selector in selectors:
        loc = page.locator(selector)
        if await loc.count():
            text = await loc.first.text_content()
            if text and text.strip():
                return " ".join(text.split())
    return ""
