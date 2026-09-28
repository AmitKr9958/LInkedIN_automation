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
_DEGREE_INLINE = re.compile(r"^(\u2022\s*\d+(?:st|nd|rd|th)\+?)\s*(.*)$")


def _normalize_card_lines(lines: list[str]) -> list[str]:
    """Split single-line 'Name • 2nd Headline' cards into separate lines."""
    out = []
    for line in lines:
        if "\u2022" not in line:
            out.append(line)
            continue
        before, _, tail = line.partition("\u2022")
        match = _DEGREE_INLINE.match("\u2022" + tail)
        if match and (before.strip() or match.group(2).strip()):
            out.extend(
                part
                for part in (before.strip(), match.group(1), match.group(2))
                if part
            )
        else:
            out.append(line)
    return out


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


def _name_from_lines(lines: list[str]) -> str:
    """The name sits on the line before the '• Nth' degree line (or first)."""
    for index, line in enumerate(lines):
        if _DEGREE_LINE.match(line):
            return lines[index - 1] if index > 0 else ""
    return lines[0] if lines else ""


async def _first_named_link(card) -> tuple[str, str]:
    links = card.locator("a[href*='/in/']")
    for index in range(min(await links.count(), 5)):
        candidate = links.nth(index)
        label = strip_degree(await candidate.inner_text() or "")
        if label and not label.lower().startswith("view "):
            return label, (await candidate.get_attribute("href")) or ""
    return "", ""


async def _sdui_search(page) -> list[Person]:
    # 2026 SDUI search results render person cards as role=listitem.
    # Virtualized lists detach nodes mid-iteration, so take a single DOM
    # snapshot instead of walking locators one by one.
    script = (
        "() => Array.from(document.querySelectorAll(\"main div[role='listitem']\"))"
        ".slice(0, 50).map(card => {"
        "const links = Array.from(card.querySelectorAll(\"a[href*='/in/']\"));"
        "const named = links.slice(0, 5).find(a => a.innerText &&"
        " !a.innerText.trim().toLowerCase().startsWith('view '));"
        "const link = named || links[0];"
        "return {text: card.innerText || '',"
        " author: named ? named.innerText.trim() : '',"
        " href: link ? (link.getAttribute('href') || '') : ''};})"
    )
    rows: list = []
    for attempt in range(3):
        try:
            rows = await page.evaluate(script) or []
        except Exception:
            rows = []
        if rows:
            break
        if attempt < 2:
            # SDUI results render client-side; early snapshots can race
            # hydration or an in-flight re-navigation ("execution context
            # was destroyed"). Wait and try again.
            try:
                await page.wait_for_timeout(3000)
            except Exception:
                pass
    if not rows:
        return []
    out = []
    for row in rows:
        href = row.get("href") or ""
        if not href:
            continue
        lines = [clean_text(line) for line in (row.get("text") or "").splitlines()]
        lines = [line for line in lines if line]
        lines = _normalize_card_lines(lines)
        headline, person_location = _headline_and_location(lines)
        name = strip_degree(row.get("author") or "")
        if not name:
            # 2026 SDUI name links can carry no visible text; the name is
            # still the card line above the '• Nth' degree line.
            name = _name_from_lines(lines)
        out.append(
            Person(
                name=name,
                headline=headline,
                location=person_location,
                href=href,
                text=" ".join(lines),
            )
        )
    return dedupe_by(out, lambda person: person.href or person.name)


_LOCATION_ALIASES = {
    "gurgaon": {"gurgaon", "gurugram", "gurugram, haryana", "gurgaon, haryana", "gurgaon, india", "gurugram, india"},
    "gurugram": {"gurgaon", "gurugram", "gurugram, haryana", "gurgaon, haryana", "gurgaon, india", "gurugram, india"},
    "delhi": {"delhi", "new delhi", "delhi, india", "new delhi, india", "national capital territory of delhi"},
    "noida": {"noida", "noida, uttar pradesh", "noida, india"},
}

def _location_matches(person_location: str, requested: str) -> bool:
    requested = clean_text(requested).lower().strip()
    actual = clean_text(person_location).lower().strip()
    if not requested:
        return True
    aliases = _LOCATION_ALIASES.get(requested, {requested})
    return any(alias in actual for alias in aliases)


def _filter_by_location(people: list[Person], requested: str) -> list[Person]:
    if not requested:
        return people
    return [person for person in people if _location_matches(person.location, requested)]


async def search(page, query: str, location: str = "") -> list[Person]:
    # LinkedIn expects a numeric geo URN here, not a city name such as
    # "Gurgaon". Sending the city string as geoUrn silently produces broad
    # results. Use the search keywords for discovery, then enforce the
    # requested city against the parsed card location.
    search_query = f"{query} {location}".strip() if location else query
    params = f"keywords={quote_plus(search_query)}&origin=GLOBAL_SEARCH_HEADER"
    await page.goto(
        f"{settings.linkedin_base_url}/search/results/people/?{params}",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    try:
        await page.wait_for_selector(
            "li.reusable-search__result-container, .entity-result, main div[role='listitem']",
            timeout=12_000,
        )
    except Exception:
        pass  # read whatever rendered
    cards = page.locator("li.reusable-search__result-container, .entity-result")
    if not await cards.count():
        return await _sdui_search(page)
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
        lines = _normalize_card_lines(lines)
        headline, person_location = _headline_and_location(lines)
        if not name:
            name = _name_from_lines(lines)
        out.append(
            Person(
                name=name,
                headline=headline,
                location=person_location,
                href=href or "",
                text=" ".join(lines),
            )
        )
    out = dedupe_by(out, lambda person: person.href or person.name)
    out = _filter_by_location(out, location)
    if not out:
        # Transient server-rendered shells can match legacy selectors before
        # SDUI hydration replaces them; fall back to the SDUI snapshot.
        sdui_people = await _sdui_search(page)
        return _filter_by_location(sdui_people, location)
    return out
