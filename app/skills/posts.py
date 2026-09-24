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


async def search(page, query: str) -> list[Post]:
    await page.goto(
        f"{settings.linkedin_base_url}/search/results/content/?keywords={quote_plus(query)}",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    cards = page.locator("div.feed-shared-update-v2, .occludable-update")
    if not await cards.count():
        # 2026 SDUI search feed marks each post card with an update-card key.
        cards = page.locator("[componentkey^='update-card']")
    out = []
    for i in range(min(await cards.count(), 50)):
        card = cards.nth(i)
        text = clean_text(await card.inner_text())
        author, link = await _first_named_link(card)
        out.append(Post(author=author, text=text, href=link))
    # Key by text so distinct posts from the same author are not collapsed.
    return dedupe_by(out, lambda post: f"{post.text[:200]}|{post.href}")
