from contextlib import asynccontextmanager
from playwright.async_api import BrowserContext, async_playwright

from .config import settings

@asynccontextmanager
async def linkedin_browser():
    async with async_playwright() as pw:
        context: BrowserContext = await pw.chromium.launch_persistent_context(
            user_data_dir=str(settings.profile_path),
            headless=settings.headless,
            viewport={"width": 1440, "height": 900},
        )
        try:
            yield context
        finally:
            await context.close()
