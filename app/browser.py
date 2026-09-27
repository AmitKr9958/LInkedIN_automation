from contextlib import asynccontextmanager

from playwright.async_api import BrowserContext, Error as PlaywrightError, async_playwright

from .config import settings


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
    # When "headless" is requested, still prefer a real window placed off-screen
    # if the operator sets HEADLESS_OFFSCREEN=true. LinkedIn session cookies from
    # a headed login often restore more reliably in a non-headless Chromium
    # process. Default remains true headless when HEADLESS=true.
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
        except PlaywrightError as exc:
            detail = str(exc).lower()
            if "user data directory is already in use" in detail or "singleton" in detail:
                reason = (
                    "the local browser profile is already in use "
                    f"(profile: {settings.profile_path})"
                )
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
