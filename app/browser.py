import asyncio
from contextlib import asynccontextmanager

from playwright.async_api import BrowserContext, Error as PlaywrightError, async_playwright

from .config import settings


PROFILE_LOCK_RETRY_ATTEMPTS = 6
PROFILE_LOCK_RETRY_DELAY_SECONDS = 10.0


def _is_profile_busy_error(exc: BaseException) -> bool:
    """Return True only for errors indicating the persistent profile is busy."""
    detail = str(exc).lower()
    return any(
        marker in detail
        for marker in (
            "user data directory is already in use",
            "user data directory is locked",
            "profile is in use",
            "profile is locked",
            "singleton",
        )
    )


def _launch_args() -> list[str]:
    """Stable Chromium flags for persistent LinkedIn profile use.

    No stealth/evasion flags. Goal is reliable profile load/flush, not
    bypassing LinkedIn security checks.
    """
    args = [
        # Keep the native scrollbar visible in the headed automation browser.
        "--disable-features=OverlayScrollbar",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--window-size=1440,900",
    ]
    # Scheduled runs use genuine headless Chromium. Interactive authentication
    # is performed separately with HEADLESS=false via the login command.
    return args


@asynccontextmanager
async def linkedin_browser(*, headless: bool | None = None):
    """Open the user's persistent local LinkedIn browser profile.

    Authentication is performed by the user in the visible browser. This
    helper never reads or exports passwords, cookies, or session tokens.

    The context is always closed on exit so Chromium can flush the user-data
    directory (cookies, local storage) to disk. Callers that perform an
    interactive login should settle on an authenticated page and wait a few
    seconds before exiting this context manager.

    ``headless`` overrides ``settings.headless`` for this launch only.
    """
    use_headless = settings.headless if headless is None else headless
    async with async_playwright() as pw:
        last_error: PlaywrightError | None = None
        for attempt in range(1, PROFILE_LOCK_RETRY_ATTEMPTS + 1):
            try:
                context: BrowserContext = await pw.chromium.launch_persistent_context(
                    user_data_dir=str(settings.profile_path),
                    headless=use_headless,
                    viewport={"width": 1440, "height": 900},
                    args=_launch_args(),
                    timeout=45_000,
                    accept_downloads=False,
                    # Consistent locale helps session restore match the login browser.
                    locale="en-US",
                )
                break
            except PlaywrightError as exc:
                last_error = exc
                if not _is_profile_busy_error(exc):
                    detail = str(exc).lower()
                    if "executable doesn't exist" in detail or "browsertype.launch" in detail:
                        reason = "Chromium is not installed"
                    else:
                        reason = "Chromium could not be started"
                    raise RuntimeError(
                        f"{reason}: {exc}. "
                        "If Chromium is installed, inspect the browser/profile error above."
                    ) from exc
                if attempt >= PROFILE_LOCK_RETRY_ATTEMPTS:
                    raise RuntimeError(
                        "the local browser profile remained in use after "
                        f"{PROFILE_LOCK_RETRY_ATTEMPTS} launch attempts "
                        f"(profile: {settings.profile_path}). "
                        "Close the other Chromium/agent session and retry."
                    ) from exc
                await asyncio.sleep(PROFILE_LOCK_RETRY_DELAY_SECONDS)

        if last_error is not None:
            raise RuntimeError(f"Chromium could not be started: {last_error}") from last_error
        try:
            yield context
        finally:
            # Close pages first so pending navigations finish, then close the
            # context so the persistent profile is flushed to disk.
            try:
                for page in list(context.pages):
                    try:
                        if not page.is_closed():
                            await page.close()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                await context.close()
            except Exception:
                # Avoid masking the original error from the with-block body.
                pass
