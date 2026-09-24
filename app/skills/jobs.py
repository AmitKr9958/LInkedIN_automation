from __future__ import annotations
from dataclasses import dataclass, asdict
from urllib.parse import quote_plus
from ..config import settings

@dataclass
class Job:
    title: str
    company: str = ""
    location: str = ""
    href: str = ""
    text: str = ""

    def to_dict(self): return asdict(self)

async def search(page, keywords: str, location: str = "", start: int = 0) -> list[Job]:
    params = f"keywords={quote_plus(keywords)}"
    if location: params += f"&location={quote_plus(location)}"
    if start: params += f"&start={start}"
    await page.goto(f"{settings.linkedin_base_url}/jobs/search/?{params}", wait_until="domcontentloaded")
    cards = page.locator("li.jobs-search-results__list-item, .job-card-container, [data-occludable-job-id]")
    result: list[Job] = []
    for i in range(min(await cards.count(), 50)):
        card = cards.nth(i)
        text = " ".join((await card.inner_text()).split())
        link = card.locator("a[href*='/jobs/view/']").first
        href = await link.get_attribute("href") if await link.count() else ""
        title = ""
        for sel in ["a[href*='/jobs/view/']", ".job-card-list__title", ".artdeco-entity-lockup__title"]:
            loc = card.locator(sel)
            if await loc.count():
                title = " ".join(((await loc.first.text_content()) or "").split())
                if title: break
        result.append(Job(title=title, href=href or "", text=text))
    return result
