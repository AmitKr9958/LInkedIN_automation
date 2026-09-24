from __future__ import annotations

from dataclasses import dataclass, asdict

from ..config import settings
from .parsing import clean_text, dedupe_by


@dataclass
class SavedItem:
    text: str
    href: str = ""

    def to_dict(self):
        return asdict(self)


async def read_saved_posts(page) -> list[SavedItem]:
    await page.goto(
        f"{settings.linkedin_base_url}/my-items/saved-posts/",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    cards = page.locator("div.feed-shared-update-v2, .occludable-update")
    if not await cards.count():
        # 2026 saved-items list marks each card with its activity urn.
        cards = page.locator("[data-chameleon-result-urn]")
    out = []
    for i in range(min(await cards.count(), 50)):
        card = cards.nth(i)
        text = clean_text(await card.inner_text())
        link = card.locator("a[href*='/feed/update/'], a[href*='/posts/']").first
        href = await link.get_attribute("href") if await link.count() else ""
        out.append(SavedItem(text=text, href=href or ""))
    return dedupe_by(out, lambda item: item.href or item.text)
