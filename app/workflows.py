from __future__ import annotations

import time

from .browser import linkedin_browser
from .config import settings
from .linkedin_reader import current_session_state

# How long the interactive login command waits for the user to finish signing in.
LOGIN_WAIT_SECONDS = 15 * 60
# Extra settle time after auth is detected so Chromium can flush cookies/storage
# into the persistent user-data directory before the context closes.
# Headless relaunch after a short settle was a common failure mode; 15s is safer.
SESSION_SETTLE_MS = 15_000


async def login_check(
    wait_for_login: bool = True,
    keep_open: bool = False,
    open_url: str = "",
    *,
    force_headed: bool = False,
):
    """Open the persistent browser profile and report/await LinkedIn authentication.

    When ``keep_open=True`` (used by ``python -m app login``), a visible browser
    stays open until the feed is authenticated or the wait budget expires.
    After authentication is detected the session is settled on the feed and a
    short delay is applied so the persistent profile can flush cookies to disk
    before the context closes. Credentials are never read or exported.
    """
    action = "login"
    previous_headless = settings.headless
    if force_headed or keep_open:
        # Interactive login must always show a real browser window.
        settings.headless = False

    try:
        async with linkedin_browser() as browser:
            page = browser.pages[0] if browser.pages else await browser.new_page()
            target = open_url or settings.linkedin_base_url
            await page.goto(target, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(3000)
            state = await current_session_state(page)

            if not state["authenticated"] and wait_for_login:
                if not keep_open:
                    return type(
                        "Result",
                        (),
                        {"action": action, "status": "unauthenticated", "details": state},
                    )()

                # Interactive wait: poll until the feed is authenticated or the
                # budget expires. The user completes CAPTCHA/OTP/password in the
                # visible browser; this process never asks for those values.
                deadline = time.monotonic() + LOGIN_WAIT_SECONDS
                while time.monotonic() < deadline:
                    try:
                        if page.is_closed():
                            break
                        state = await current_session_state(page)
                        if state["authenticated"]:
                            break
                    except Exception:
                        # Page navigations during login can briefly invalidate
                        # handles; keep polling until the budget is exhausted.
                        pass
                    await page.wait_for_timeout(2000)
                else:
                    # Timed out still unauthenticated.
                    state = await _safe_session_state(page)
                    return type(
                        "Result",
                        (),
                        {"action": action, "status": "unauthenticated", "details": state},
                    )()

            if state["authenticated"] and keep_open:
                # Land on the feed so LinkedIn finishes writing session cookies,
                # then wait long enough for Chromium to flush the profile.
                # A second navigation improves cookie durability for the next
                # headless launch of the same user-data directory.
                try:
                    if page.is_closed():
                        pass
                    else:
                        feed_url = f"{settings.linkedin_base_url.rstrip('/')}/feed/"
                        url_lower = (page.url or "").lower()
                        if "/feed" not in url_lower:
                            await page.goto(
                                feed_url,
                                wait_until="domcontentloaded",
                                timeout=60_000,
                            )
                        await page.wait_for_timeout(SESSION_SETTLE_MS // 2)
                        # Soft second hop: jobs page then back to feed.
                        try:
                            await page.goto(
                                f"{settings.linkedin_base_url.rstrip('/')}/jobs/",
                                wait_until="domcontentloaded",
                                timeout=60_000,
                            )
                            await page.wait_for_timeout(2_000)
                            await page.goto(
                                feed_url,
                                wait_until="domcontentloaded",
                                timeout=60_000,
                            )
                        except Exception:
                            pass
                        await page.wait_for_timeout(SESSION_SETTLE_MS // 2)
                        state = await current_session_state(page)
                except Exception:
                    # Best-effort settle; still report the last known state.
                    state = await _safe_session_state(page)

            status = "authenticated" if state.get("authenticated") else "unauthenticated"

        # The first context only proves that LinkedIn accepted the login while
        # the browser was open. For interactive login, verify the actual
        # persistence boundary by closing that context and reopening the same
        # profile. This prevents the CLI from claiming a session was saved when
        # Chromium did not commit it to disk.
        if status == "authenticated" and keep_open:
            try:
                async with linkedin_browser() as verify_browser:
                    verify_page = (
                        verify_browser.pages[0]
                        if verify_browser.pages
                        else await verify_browser.new_page()
                    )
                    verify_state = await current_session_state(verify_page)
                if not verify_state.get("authenticated"):
                    state = {
                        **state,
                        "authenticated": False,
                        "confidence": verify_state.get("confidence", "high"),
                        "persistence_verified": False,
                        "persistence_check": verify_state,
                        "note": (
                            "LinkedIn was authenticated in the interactive browser, "
                            "but the same persistent profile was unauthenticated "
                            "after Chromium closed and reopened it."
                        ),
                    }
                    status = "persistence_failed"
                else:
                    state = {
                        **state,
                        "authenticated": True,
                        "persistence_verified": True,
                        "persistence_check": verify_state,
                    }
            except Exception as exc:
                state = {
                    **state,
                    "persistence_verified": False,
                    "persistence_check_error": f"{type(exc).__name__}: {exc}",
                    "note": "The interactive session was authenticated, but persistence could not be verified after reopening the profile.",
                }
                status = "persistence_check_failed"

        return type("Result", (), {"action": action, "status": status, "details": state})()
    finally:
        settings.headless = previous_headless


async def _safe_session_state(page) -> dict:
    try:
        if page is None or page.is_closed():
            return {
                "url": "",
                "title": "",
                "authenticated": False,
                "confidence": "low",
                "note": "browser page closed before session could be verified",
            }
        return await current_session_state(page)
    except Exception as exc:
        return {
            "url": "",
            "title": "",
            "authenticated": False,
            "confidence": "low",
            "note": f"session check failed: {type(exc).__name__}: {exc}",
        }
