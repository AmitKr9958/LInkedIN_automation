from __future__ import annotations
from ..browser import linkedin_browser
from ..linkedin_reader import current_session_state
from ..config import settings

async def check() -> dict:
    async with linkedin_browser() as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()
        await page.goto(settings.linkedin_base_url, wait_until="domcontentloaded")
        return await current_session_state(page)
