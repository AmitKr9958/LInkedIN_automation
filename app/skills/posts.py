from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from urllib.parse import quote_plus

from ..config import settings
from .parsing import clean_text, dedupe_by, strip_degree


_POST_AGE_RE = re.compile(
    r"(?i)\\b(?:"
    r"just now|now|today|yesterday|"
    r"(\\d+)\\s*(minute|minutes|min|mins|hour|hours|hr|hrs|day|days|week|weeks|month|months)"
    r"\\s*(?:ago)?|"
    r"(\\d+)\\s*(m|h|d|w)"
    r")\\b"
)


def _posted_age(value: str) -> tuple[str, float | None]:
    text = " ".join((value or "").split())
    match = _POST_AGE_RE.search(text)
    if not match:
        return "", None
    raw = match.group(0).strip()
    lower = raw.lower()
    if lower in {"just now", "now", "today"}:
        return raw, 0.0
    if lower == "yesterday":
        return raw, 24.0
    number = match.group(1) or match.group(3)
    unit = (match.group(2) or match.group(4) or "").lower()
    if number is None:
        return raw, None
    amount = float(number)
    if unit.startswith("m"):
        return raw, amount / 60.0
    if unit.startswith("h"):
        return raw, amount
    if unit.startswith("d"):
        return raw, amount * 24.0
    if unit.startswith("w"):
        return raw, amount * 24.0 * 7.0
    if unit.startswith("month"):
        return raw, amount * 24.0 * 30.0
    return raw, None


@dataclass
class Post:
    author: str
    text: str = ""
    href: str = ""
    posted: str = ""
    posted_hours: float | None = None

    def to_dict(self):
        return asdict(self)


async def _first_named_link(card) -> tuple[str, str]:
    links = card.locator("a[href*='/in/']")
    for index in range(min(await links.count(), 5)):
        candidate = links.nth(index)
        label = strip_degree(await candidate.inner_text() or "")
        if label and not label.lower().startswith("view "):
            return label, (await candidate.get_attribute("href")) or ""
    return "", ""


def _snapshot_posts(rows: list[dict]) -> list[Post]:
    out = []
    for row in rows:
        text = clean_text(row.get("text") or "")
        posted, posted_hours = _posted_age(text)
        out.append(
            Post(
                author=strip_degree(row.get("author") or ""),
                text=text,
                href=row.get("href") or "",
                posted=posted,
                posted_hours=posted_hours,
            )
        )
    return dedupe_by(out, lambda post: f"{post.text[:240]}|{post.href}")


async def _sdui_search(page) -> list[Post]:
    script = (
        "() => Array.from(document.querySelectorAll(\"[componentkey^='update-card']\"))"
        ".slice(0, 100).map(card => {"
        "const named = Array.from(card.querySelectorAll(\"a[href*='/in/']\"))"
        ".slice(0, 5).find(a => a.innerText &&"
        " !a.innerText.trim().toLowerCase().startsWith('view '));"
        "return {text: card.innerText || '',"
        " author: named ? named.innerText.trim() : '',"
        " href: named ? (named.getAttribute('href') || '') : ''};})"
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
            try:
                await page.wait_for_timeout(3000)
            except Exception:
                pass
    return _snapshot_posts(rows)


async def _legacy_search(page) -> list[Post]:
    cards = page.locator("div.feed-shared-update-v2, .occludable-update")
    if not await cards.count():
        return []
    rows = []
    for i in range(min(await cards.count(), 100)):
        card = cards.nth(i)
        try:
            text = await card.inner_text()
            author, link = await _first_named_link(card)
            rows.append({"author": author, "text": text, "href": link})
        except Exception:
            continue
    return _snapshot_posts(rows)


async def search(page, query: str) -> list[Post]:
    await page.goto(
        f"{settings.linkedin_base_url}/search/results/content/?keywords={quote_plus(query)}",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    try:
        await page.wait_for_selector(
            "div.feed-shared-update-v2, .occludable-update, [componentkey^='update-card']",
            timeout=12_000,
        )
    except Exception:
        pass
    out = await _legacy_search(page)
    if not out:
        out = await _sdui_search(page)
    return out


async def read_feed(page, *, max_scrolls: int = 6) -> list[Post]:
    """Read the authenticated personalized LinkedIn home feed.

    This is intentionally read-only. It scrolls the feed to load additional
    cards, snapshots visible post cards, and never likes, comments, follows,
    connects, or messages anyone.
    """
    await page.goto(
        f"{settings.linkedin_base_url}/feed/",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    try:
        await page.wait_for_selector(
            "div.feed-shared-update-v2, .occludable-update, [componentkey^='update-card']",
            timeout=12_000,
        )
    except Exception:
        pass

    collected: dict[str, Post] = {}
    unchanged = 0
    for _ in range(max_scrolls + 1):
        batch = await _legacy_search(page)
        if not batch:
            batch = await _sdui_search(page)
        before = len(collected)
        for post in batch:
            key = f"{post.text[:240]}|{post.href}"
            collected[key] = post
        if len(collected) == before:
            unchanged += 1
        else:
            unchanged = 0
        if unchanged >= 2:
            break
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2500)
        except Exception:
            break

    return list(collected.values())
