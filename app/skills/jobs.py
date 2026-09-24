from __future__ import annotations

from dataclasses import dataclass, asdict
from urllib.parse import quote_plus, urljoin

from ..config import settings

@dataclass
class Job:
    title: str
    company: str = ""
    location: str = ""
    href: str = ""
    posted: str = ""
    easy_apply: bool = False
    text: str = ""

    def to_dict(self):
        return asdict(self)

async def _text(card, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        loc = card.locator(selector).first
        if await loc.count():
            value = " ".join(((await loc.text_content()) or "").split())
            if value:
                return value
    return ""

async def search(page, keywords: str, location: str = "", start: int = 0) -> list[Job]:
    params = f"keywords={quote_plus(keywords)}"
    if location:
        params += f"&location={quote_plus(location)}"
    if start:
        params += f"&start={start}"
    await page.goto(f"{settings.linkedin_base_url}/jobs/search/?{params}", wait_until="domcontentloaded")
    cards = page.locator("li.jobs-search-results__list-item, .job-card-container, [data-occludable-job-id]")
    result: list[Job] = []
    for i in range(min(await cards.count(), 50)):
        card = cards.nth(i)
        text = " ".join((await card.inner_text()).split())
        link = card.locator("a[href*='/jobs/view/']").first
        href = ""
        if await link.count():
            href = urljoin(settings.linkedin_base_url, await link.get_attribute("href") or "")
        title = await _text(card, (".job-card-list__title", ".artdeco-entity-lockup__title", "a[href*='/jobs/view/']"))
        company = await _text(card, (".artdeco-entity-lockup__subtitle", ".job-card-container__company-name", "h4"))
        location_text = await _text(card, (".job-card-container__metadata-item", ".artdeco-entity-lockup__caption", "[class*='location']"))
        posted = await _text(card, ("time", "[class*='listed-time']", "[class*='posted']"))
        result.append(Job(title=title, company=company, location=location_text, href=href,
                          posted=posted, easy_apply="easy apply" in text.lower(), text=text))
    return result
