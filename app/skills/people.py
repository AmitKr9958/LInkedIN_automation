from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from urllib.parse import quote_plus

from ..config import settings
from .parsing import clean_text, dedupe_by, strip_degree


@dataclass
class Person:
    name: str
    headline: str = ""
    location: str = ""
    href: str = ""
    text: str = ""

    def to_dict(self):
        return asdict(self)


_DEGREE_LINE = re.compile(r"^\u2022\s*\d")


def _headline_and_location(lines: list[str]) -> tuple[str, str]:
    """Parse card lines shaped as name / '• 2nd' / headline / location."""
    for index, line in enumerate(lines):
        if _DEGREE_LINE.match(line):
            headline = lines[index + 1] if index + 1 < len(lines) else ""
            location = lines[index + 2] if index + 2 < len(lines) else ""
            if "\u2022" in location:
                location = ""
            return headline, location
    return "", ""


async def _first_named_link(card) -> tuple[str, str]:
    links = card.locator("a[href*='/in/']")
    for index in range(min(await links.count(), 5)):
        candidate = links.nth(index)
        label = strip_degree(await candidate.inner_text() or "")
        if label and not label.lower().startswith("view "):
            return label, (await candidate.get_attribute("href")) or ""
    return "", ""


async def search(page, query: str, location: str = "") -> list[Person]:
    params = f"keywords={quote_plus(query)}&origin=GLOBAL_SEARCH_HEADER"
    if location:
        params += f"&geoUrn={quote_plus(location)}"
    await page.goto(
        f"{settings.linkedin_base_url}/search/results/people/?{params}",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    cards = page.locator("li.reusable-search__result-container, .entity-result")
    if not await cards.count():
        # 2026 SDUI search results render person cards as role=listitem.
        cards = page.locator("main div[role='listitem']")
    out = []
    for i in range(min(await cards.count(), 50)):
        card = cards.nth(i)
        links = card.locator("a[href*='/in/']")
        if not await links.count():
            continue
        name, href = await _first_named_link(card)
        if not href:
            href = (await links.first.get_attribute("href")) or ""
        lines = [clean_text(line) for line in (await card.inner_text()).splitlines()]
        lines = [line for line in lines if line]
        headline, person_location = _headline_and_location(lines)
        out.append(
            Person(
                name=name,
                headline=headline,
                location=person_location,
                href=href or "",
                text=" ".join(lines),
            )
        )
    return dedupe_by(out, lambda person: person.href or person.name)
