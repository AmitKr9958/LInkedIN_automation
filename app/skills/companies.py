from __future__ import annotations

from dataclasses import dataclass, asdict
from urllib.parse import quote_plus

from ..config import settings
from .parsing import clean_text, dedupe_by


@dataclass
class Company:
    name: str
    industry: str = ""
    location: str = ""
    href: str = ""
    text: str = ""

    def to_dict(self):
        return asdict(self)


async def _legacy_search(page) -> list[Company]:
    cards = page.locator("li.reusable-search__result-container, .entity-result")
    out = []
    for i in range(min(await cards.count(), 50)):
        card = cards.nth(i)
        text = clean_text(await card.inner_text())
        link = card.locator("a[href*='/company/']").first
        href = await link.get_attribute("href") if await link.count() else ""
        name = ""
        for sel in [".entity-result__title-text a", "a[href*='/company/']"]:
            loc = card.locator(sel)
            if await loc.count():
                name = clean_text(await loc.first.text_content())
                if name:
                    break
        out.append(Company(name=name, href=href or "", text=text))
    return dedupe_by(out, lambda company: company.href or company.name)


async def _sdui_search(page) -> list[Company]:
    # 2026 SDUI company cards are full-card anchors; keep one plain
    # /company/ link per href (skip query-string variants).
    anchors = page.locator("main a[href*='/company/']")
    out = []
    seen = set()
    for i in range(min(await anchors.count(), 200)):
        anchor = anchors.nth(i)
        href = (await anchor.get_attribute("href")) or ""
        if not href or "?" in href:
            continue
        key = href.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        lines = [clean_text(line) for line in (await anchor.inner_text()).splitlines()]
        lines = [line for line in lines if line and line != "Follow"]
        name = lines[0] if lines else ""
        industry = lines[1] if len(lines) > 1 and "follower" not in lines[1].lower() else ""
        out.append(Company(name=name, industry=industry, href=href, text=" ".join(lines)))
        if len(out) >= 50:
            break
    return out


async def search(page, query: str) -> list[Company]:
    await page.goto(
        f"{settings.linkedin_base_url}/search/results/companies/?keywords={quote_plus(query)}",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    if await page.locator("li.reusable-search__result-container, .entity-result").count():
        return await _legacy_search(page)
    return await _sdui_search(page)
