from dataclasses import dataclass
from .approval import require_approval
from .browser import linkedin_browser
from .config import settings

@dataclass
class WorkflowResult:
    action: str
    status: str
    details: str = ""

async def login_check() -> WorkflowResult:
    async with linkedin_browser() as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()
        await page.goto(settings.linkedin_base_url, wait_until="domcontentloaded")
        title = await page.title()
        return WorkflowResult("login_check", "ok", title)

async def open_profile() -> WorkflowResult:
    async with linkedin_browser() as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()
        await page.goto(f"{settings.linkedin_base_url}/in/", wait_until="domcontentloaded")
        return WorkflowResult("open_profile", "ready", await page.title())

async def draft_action(action: str, target: str, text: str) -> WorkflowResult:
    # Drafting is safe; execution remains behind an approval gate.
    return WorkflowResult(action, "drafted", f"target={target}; text={text}")

async def execute_action(action: str, target: str, text: str) -> WorkflowResult:
    require_approval(action)
    if settings.dry_run:
        return WorkflowResult(action, "dry_run", f"target={target}")
    # Concrete LinkedIn UI actions will be implemented per workflow after selectors
    # are validated against the user's current UI.
    return WorkflowResult(action, "not_implemented", "UI action adapter pending")
