from __future__ import annotations
from dataclasses import dataclass, asdict
from urllib.parse import quote_plus
from ..config import settings

@dataclass
class Post:
    author: str = ""
    text: str = ""
    href: str = ""
    def to_dict(self): return asdict(self)

async def search(page, query: str) -> list[Post]:
    await page.goto(f"{settings.linkedin_base_url}/search/results/content/?keywords={quote_plus(query)}", wait_until="domcontentloaded")
    cards=page.locator("div.feed-shared-update-v2, .occludable-update")
    out=[]
    for i in range(min(await cards.count(),50)):
        card=cards.nth(i); text=" ".join((await card.inner_text()).split())
        author=""; link=""
        a=card.locator("a[href*='/in/']").first
        if await a.count(): author=" ".join(((await a.text_content()) or "").split()); link=await a.get_attribute("href") or ""
        out.append(Post(author=author,text=text,href=link))
    return out
