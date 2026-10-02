import asyncio
from contextlib import asynccontextmanager

from playwright.async_api import BrowserContext, Error as PlaywrightError, async_playwright

from .config import settings


PROFILE_LOCK_RETRY_ATTEMPTS = 6
PROFILE_LOCK_RETRY_DELAY_SECONDS = 10.0
# A Chromium process can occasionally time out while starting even when the
# Playwright executable is installed. Keep this retry budget small so a real
# startup failure surfaces promptly.
CHROMIUM_START_RETRY_ATTEMPTS = 3
CHROMIUM_START_RETRY_DELAY_SECONDS = 5.0


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


def _is_chromium_startup_timeout(exc: BaseException) -> bool:
    """Return True for transient Chromium startup timeouts, not missing binaries."""
    detail = str(exc).lower()
    if "executable doesn't exist" in detail:
        return False
    return "timeout" in detail and "launch_persistent_context" in detail


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
        profile_attempt = 0
        startup_attempt = 0
        while True:
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
                if _is_profile_busy_error(exc):
                    profile_attempt += 1
                    if profile_attempt >= PROFILE_LOCK_RETRY_ATTEMPTS:
                        raise RuntimeError(
                            "the local browser profile remained in use after "
                            f"{PROFILE_LOCK_RETRY_ATTEMPTS} launch attempts "
                            f"(profile: {settings.profile_path}). "
                            "Close the other Chromium/agent session and retry."
                        ) from exc
                    await asyncio.sleep(PROFILE_LOCK_RETRY_DELAY_SECONDS)
                    continue

                if _is_chromium_startup_timeout(exc):
                    startup_attempt += 1
                    if startup_attempt >= CHROMIUM_START_RETRY_ATTEMPTS:
                        raise RuntimeError(
                            "Chromium startup timed out after "
                            f"{CHROMIUM_START_RETRY_ATTEMPTS} attempts. "
                            "Chromium is installed, but the browser process did not start in time."
                        ) from exc
                    await asyncio.sleep(CHROMIUM_START_RETRY_DELAY_SECONDS)
                    continue

                detail = str(exc).lower()
                if "executable doesn't exist" in detail:
                    reason = "Chromium is not installed"
                else:
                    reason = "Chromium could not be started"
                raise RuntimeError(
                    f"{reason}: {exc}. "
                    "If Chromium is installed, inspect the browser/profile error above."
                ) from exc

        if last_error is not None:
            raise RuntimeError(f"Chromium could not be started: {last_error}") from last_error
        try:
            yield context
        finally:
            # Let Playwright close the persistent context directly. Closing pages
            # individually can trigger page-level teardown before Chromium has
            # committed browser-managed session state to the profile. The context
            # close is the lifecycle boundary that flushes the persistent profile.
            try:
                await context.close()
            except Exception:
                # Avoid masking the original error from the with-block body.
                pass
