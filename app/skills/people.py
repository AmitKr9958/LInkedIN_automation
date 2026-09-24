from __future__ import annotations
from dataclasses import dataclass, asdict
from urllib.parse import quote_plus
from ..config import settings

@dataclass
class Person:
    name: str
    headline: str = ""
    location: str = ""
    href: str = ""
    text: str = ""
    def to_dict(self): return asdict(self)

async def search(page, query: str, location: str = "") -> list[Person]:
    params = f"keywords={quote_plus(query)}&origin=GLOBAL_SEARCH_HEADER"
    if location: params += f"&geoUrn={quote_plus(location)}"
    await page.goto(f"{settings.linkedin_base_url}/search/results/people/?{params}", wait_until="domcontentloaded")
    cards = page.locator("li.reusable-search__result-container, .entity-result")
    out=[]
    for i in range(min(await cards.count(),50)):
        card=cards.nth(i); text=" ".join((await card.inner_text()).split())
        link=card.locator("a[href*='/in/']").first
        href=await link.get_attribute("href") if await link.count() else ""
        name=""; headline=""
        for sel in [".entity-result__title-text a", "a[href*='/in/']"]:
            loc=card.locator(sel)
            if await loc.count():
                name=" ".join(((await loc.first.text_content()) or "").split())
                if name: break
        h=card.locator(".entity-result__primary-subtitle")
        if await h.count(): headline=" ".join(((await h.first.text_content()) or "").split())
        out.append(Person(name=name,headline=headline,href=href or "",text=text))
    return out
