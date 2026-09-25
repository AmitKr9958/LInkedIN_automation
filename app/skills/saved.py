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


async def _sdui_search(page) -> list[SavedItem]:
    # 2026 saved-items list marks each card with its activity urn.
    # Virtualized lists detach nodes mid-iteration, so take a single DOM
    # snapshot instead of walking locators one by one.
    script = (
        "() => Array.from(document.querySelectorAll('[data-chameleon-result-urn]'))"
        ".slice(0, 50).map(card => {"
        "const link = card.querySelector(\"a[href*='/feed/update/'], a[href*='/posts/']\");"
        "return {text: card.innerText || '',"
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
        out.append(SavedItem(text=clean_text(row.get("text") or ""), href=row.get("href") or ""))
    return dedupe_by(out, lambda item: item.href or item.text)


async def read_saved_posts(page) -> list[SavedItem]:
    await page.goto(
        f"{settings.linkedin_base_url}/my-items/saved-posts/",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    try:
        await page.wait_for_selector(
            "div.feed-shared-update-v2, .occludable-update, [data-chameleon-result-urn]",
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
        link = card.locator("a[href*='/feed/update/'], a[href*='/posts/']").first
        href = await link.get_attribute("href") if await link.count() else ""
        out.append(SavedItem(text=text, href=href or ""))
    out = dedupe_by(out, lambda item: item.href or item.text)
    if not out:
        # Transient server-rendered shells can match legacy selectors before
        # SDUI hydration replaces them; fall back to the SDUI snapshot.
        return await _sdui_search(page)
    return out
