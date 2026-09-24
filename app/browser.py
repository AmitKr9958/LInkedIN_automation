from contextlib import asynccontextmanager

from playwright.async_api import BrowserContext, Error as PlaywrightError, async_playwright

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
        except PlaywrightError as exc:
            detail = str(exc).lower()
            if "user data directory is already in use" in detail or "singleton" in detail:
                reason = "the local browser profile is already in use"
            elif "executable doesn't exist" in detail or "browserType.launch" in detail:
                reason = "Chromium is not installed"
            else:
                reason = "Chromium could not be started"
            raise RuntimeError(
                f"{reason}. Close other agent/Chromium instances using this profile "
                "or run 'python -m playwright install chromium'."
            ) from exc
        try:
            yield context
        finally:
            await context.close()
