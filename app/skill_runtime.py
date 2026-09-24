from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .browser import linkedin_browser
from .linkedin_reader import current_session_state
from .skills import companies, jobs, people, posts, profile, saved


@dataclass
class RuntimeResult:
    skill: str
    data: Any


async def run_read(skill: str, **kwargs) -> RuntimeResult:
    async with linkedin_browser() as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()

        # Never assume authentication merely because LinkedIn did not redirect
        # to /login. Fail closed when the local session cannot be verified.
        if not page.url or "linkedin.com" not in page.url:
            await page.goto("https://www.linkedin.com/", wait_until="domcontentloaded")
        state = await current_session_state(page)
        if not state["authenticated"]:
            raise RuntimeError(
                "LinkedIn session is not verified. Run 'python -m app login' "
                "with HEADLESS=false and sign in manually."
            )

        if skill == "profile":
            data = await profile.read_profile(page)
        elif skill == "jobs":
            data = await jobs.search(
                page, kwargs.get("keywords", "Power BI"), kwargs.get("location", "Gurgaon")
            )
        elif skill == "people":
            data = await people.search(page, kwargs.get("query", "Power BI recruiter"))
        elif skill == "companies":
            data = await companies.search(page, kwargs.get("query", "technology"))
        elif skill == "posts":
            data = await posts.search(page, kwargs.get("query", "Power BI"))
        elif skill == "saved":
            data = await saved.read_saved_posts(page)
        else:
            raise ValueError(f"Unsupported read skill: {skill}")

        if hasattr(data, "to_dict"):
            data = data.to_dict()
        elif isinstance(data, list):
            data = [x.to_dict() if hasattr(x, "to_dict") else x for x in data]
        return RuntimeResult(skill, data)
