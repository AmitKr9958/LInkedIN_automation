from __future__ import annotations
from dataclasses import dataclass, asdict
from urllib.parse import quote_plus
from ..config import settings
from .parsing import dedupe_by

@dataclass
class Company:
    name: str
    industry: str = ""
    location: str = ""
    href: str = ""
    text: str = ""
    def to_dict(self): return asdict(self)

async def search(page, query: str) -> list[Company]:
    await page.goto(f"{settings.linkedin_base_url}/search/results/companies/?keywords={quote_plus(query)}", wait_until="domcontentloaded")
    cards=page.locator("li.reusable-search__result-container, .entity-result")
    out=[]
    for i in range(min(await cards.count(),50)):
        card=cards.nth(i); text=" ".join((await card.inner_text()).split())
        link=card.locator("a[href*='/company/']").first
        href=await link.get_attribute("href") if await link.count() else ""
        name=""
        for sel in [".entity-result__title-text a","a[href*='/company/']"]:
            loc=card.locator(sel)
            if await loc.count():
                name=" ".join(((await loc.first.text_content()) or "").split())
                if name: break
        out.append(Company(name=name,href=href or "",text=text))
    return dedupe_by(out, lambda company: company.href or company.name)
