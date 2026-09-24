from __future__ import annotations
from dataclasses import dataclass, asdict
from ..config import settings

@dataclass
class SavedItem:
    text: str = ""
    href: str = ""
    def to_dict(self): return asdict(self)

async def read_saved_posts(page) -> list[SavedItem]:
    await page.goto(f"{settings.linkedin_base_url}/my-items/saved-posts/", wait_until="domcontentloaded")
    cards=page.locator("div.feed-shared-update-v2, .occludable-update")
    out=[]
    for i in range(min(await cards.count(),50)):
        card=cards.nth(i); text=" ".join((await card.inner_text()).split())
        out.append(SavedItem(text=text))
    return out
