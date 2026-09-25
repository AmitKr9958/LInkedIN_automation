from __future__ import annotations

from dataclasses import dataclass, asdict
from urllib.parse import quote_plus

from ..config import settings
from .parsing import clean_text, dedupe_by, strip_degree


@dataclass
class Post:
    author: str
    text: str = ""
    href: str = ""

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


async def _sdui_search(page) -> list[Post]:
    # 2026 SDUI search feed marks each post card with an update-card key.
    # Virtualized lists detach nodes mid-iteration, so take a single DOM
    # snapshot instead of walking locators one by one.
    script = (
        "() => Array.from(document.querySelectorAll(\"[componentkey^='update-card']\"))"
        ".slice(0, 50).map(card => {"
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
        out.append(
            Post(
                author=strip_degree(row.get("author") or ""),
                text=clean_text(row.get("text") or ""),
                href=row.get("href") or "",
            )
        )
    # Key by text so distinct posts from the same author are not collapsed.
    return dedupe_by(out, lambda post: f"{post.text[:200]}|{post.href}")


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
        pass  # read whatever rendered
    cards = page.locator("div.feed-shared-update-v2, .occludable-update")
    if not await cards.count():
        return await _sdui_search(page)
    out = []
    for i in range(min(await cards.count(), 50)):
        card = cards.nth(i)
        text = clean_text(await card.inner_text())
        author, link = await _first_named_link(card)
        out.append(Post(author=author, text=text, href=link))
    # Key by text so distinct posts from the same author are not collapsed.
    out = dedupe_by(out, lambda post: f"{post.text[:200]}|{post.href}")
    if not out:
        # Transient server-rendered shells can match legacy selectors before
        # SDUI hydration replaces them; fall back to the SDUI snapshot.
        return await _sdui_search(page)
    return out
