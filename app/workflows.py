from __future__ import annotations

import asyncio

from .browser import linkedin_browser
from .config import settings
from .linkedin_reader import current_session_state


async def login_check(wait_for_login: bool = True, keep_open: bool = False, open_url: str = ""):
    action = "login"
    async with linkedin_browser() as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()
        await page.goto(open_url or settings.linkedin_base_url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(3000)
        state = await current_session_state(page)
        if not state["authenticated"] and wait_for_login:
            if keep_open:
                while True:
                    state = await current_session_state(page)
                    if state["authenticated"]:
                        break
                    await page.wait_for_timeout(2000)
            else:
                return type("Result", (), {"action": action, "status": "unauthenticated", "details": state})()
        if keep_open:
            await page.wait_for_timeout(500)
        return type("Result", (), {"action": action, "status": "authenticated" if state["authenticated"] else "unauthenticated", "details": state})()
