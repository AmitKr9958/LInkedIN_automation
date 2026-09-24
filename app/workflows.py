import asyncio
from dataclasses import dataclass
from urllib.parse import quote_plus

from .approval import require_approval
from .browser import linkedin_browser
from .config import settings
from .linkedin_reader import current_session_state

LOGIN_WAIT_SECONDS = 300
LOGIN_POLL_SECONDS = 2


@dataclass
class WorkflowResult:
    action: str
    status: str
    details: str = ""


async def login_check(wait_for_login: bool = True, keep_open: bool = False) -> WorkflowResult:
    """Open a visible persistent browser and wait for manual LinkedIn login.

    The user performs authentication directly in the browser. Credentials,
    OTPs, passwords, cookies, and session tokens are never requested,
    exported, or logged by this workflow.
    """
    async with linkedin_browser() as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()
        await page.goto(settings.linkedin_base_url, wait_until="domcontentloaded")

        state = await current_session_state(page)
        # A root URL can retain an authenticated LinkedIn title while the app
        # redirects asynchronously to /feed/. Give the browser a brief chance
        # to finish that redirect before classifying the session.
        if not state["authenticated"] and wait_for_login:
            try:
                await page.wait_for_url("**/feed/**", timeout=5_000)
                state = await current_session_state(page)
            except Exception:
                pass

        if state["authenticated"] or not wait_for_login:
            status = "ok" if state["authenticated"] else "not_authenticated"
            result = WorkflowResult("login_check", status, str(state))
            if keep_open and state["authenticated"]:
                await asyncio.to_thread(input, "LinkedIn session is ready. Press Enter to close the browser... ")
            return result

        deadline = asyncio.get_running_loop().time() + LOGIN_WAIT_SECONDS
        while asyncio.get_running_loop().time() < deadline:
            await page.wait_for_timeout(LOGIN_POLL_SECONDS * 1000)
            state = await current_session_state(page)
            if state["authenticated"]:
                result = WorkflowResult("login_check", "ok", str(state))
                if keep_open:
                    await asyncio.to_thread(input, "LinkedIn login detected. Press Enter to close the browser... ")
                return result

        return WorkflowResult(
            "login_check",
            "timeout",
            f"LinkedIn authentication was not detected within {LOGIN_WAIT_SECONDS} seconds: {state}",
        )


async def open_profile() -> WorkflowResult:
    async with linkedin_browser() as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()
        await page.goto(f"{settings.linkedin_base_url}/in/", wait_until="domcontentloaded")
        state = await current_session_state(page)
        status = "ready" if state["authenticated"] else "not_authenticated"
        return WorkflowResult("open_profile", status, str(state))


async def search_jobs(keywords: str = "Power BI", location: str = "Gurgaon") -> WorkflowResult:
    async with linkedin_browser() as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()
        url = f"{settings.linkedin_base_url}/jobs/search/?keywords={quote_plus(keywords)}&location={quote_plus(location)}"
        await page.goto(url, wait_until="domcontentloaded")
        state = await current_session_state(page)
        status = "read_only" if state["authenticated"] else "not_authenticated"
        return WorkflowResult("search_jobs", status, str(state))


async def draft_action(action: str, target: str, text: str) -> WorkflowResult:
    return WorkflowResult(action, "drafted", f"target={target}; text={text}")


async def execute_action(action: str, target: str, text: str) -> WorkflowResult:
    require_approval(action)
    if settings.dry_run:
        return WorkflowResult(action, "dry_run", f"target={target}")
    return WorkflowResult(action, "not_implemented", "UI action adapter pending")
