from dataclasses import dataclass, asdict
from typing import Any
from playwright.async_api import Page

from .linkedin_selectors import JOB_CARD_SELECTORS

@dataclass
class JobListing:
    title: str = ""
    company: str = ""
    location: str = ""
    url: str = ""
    posted: str = ""

async def current_session_state(page: Page) -> dict[str, Any]:
    url = page.url
    title = await page.title()
    return {"url": url, "title": title, "authenticated": "/login" not in url.lower()}

async def read_job_cards(page: Page) -> list[dict[str, Any]]:
    selector = ", ".join(JOB_CARD_SELECTORS)
    cards = await page.locator(selector).all()
    result = []
    for card in cards:
        text = (await card.inner_text()).strip()
        link = card.locator("a").first
        href = await link.get_attribute("href") if await link.count() else ""
        result.append(asdict(JobListing(url=href or "", title=text.splitlines()[0] if text else "", company="", location="", posted="")))
    return result
