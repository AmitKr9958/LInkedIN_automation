from contextlib import asynccontextmanager

from playwright.async_api import BrowserContext, TimeoutError as PlaywrightTimeoutError, async_playwright

from .config import settings

@asynccontextmanager
async def linkedin_browser():
    """Open the user's persistent local LinkedIn browser profile.

    Authentication is performed by the user in the visible browser. This
    helper never reads or exports passwords, cookies, or session tokens.
    """
    async with async_playwright() as pw:
        try:
            context: BrowserContext = await pw.chromium.launch_persistent_context(
                user_data_dir=str(settings.profile_path),
                headless=settings.headless,
                viewport={"width": 1440, "height": 900},
                timeout=30_000,
            )
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(
                "Could not start Chromium. Run 'python -m playwright install chromium' "
                "and verify that the local browser profile is not already locked."
            ) from exc
        try:
            yield context
        finally:
            await context.close()
