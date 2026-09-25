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
    diagnostics: dict | None = None


def _filter_jobs_by_freshness(
    data: list[Any],
    max_posted_hours: float | None = 48,
    diagnostics: dict | None = None,
) -> list[Any]:
    """Keep fresh jobs plus records whose posting age could not be determined."""
    if max_posted_hours is None:
        if diagnostics is not None:
            diagnostics["freshness_window_hours"] = None
        return data
    kept: list[Any] = []
    rejected = 0
    for job in data:
        if getattr(job, "posted_hours", None) is None or job.posted_hours <= max_posted_hours:
            kept.append(job)
        else:
            rejected += 1
    if diagnostics is not None:
        diagnostics["freshness_window_hours"] = max_posted_hours
        diagnostics["rejected_freshness"] = rejected
        diagnostics["returned_after_freshness"] = len(kept)
    return kept


async def run_read(skill: str, **kwargs) -> RuntimeResult:
    async with linkedin_browser() as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()

        # Never assume authentication merely because LinkedIn did not redirect
        # to /login. Fail closed when the local session cannot be verified.
        # Start from the authenticated feed so LinkedIn can restore the
        # persistent session before we inspect authentication state.
        if not page.url or "linkedin.com" not in page.url or "/feed/" not in page.url:
            for attempt in range(2):
                try:
                    await page.goto(
                        "https://www.linkedin.com/feed/",
                        wait_until="domcontentloaded",
                        timeout=60_000,
                    )
                    break
                except Exception:
                    if attempt == 1:
                        raise
                    await page.wait_for_timeout(2000)
        await page.wait_for_timeout(3000)
        state = await current_session_state(page)
        if not state["authenticated"]:
            raise RuntimeError(
                "LinkedIn session is not verified. Run 'python -m app login' "
                "with HEADLESS=false and sign in manually."
            )

        if skill == "profile":
            data = await profile.read_profile(page)
        elif skill == "jobs":
            diagnostics: dict = {"skill": "jobs"}
            data = await jobs.search(
                page,
                kwargs.get("keywords", "Power BI"),
                kwargs.get("location", "Gurgaon"),
                start=kwargs.get("start", 0),
                diagnostics=diagnostics,
            )
            # Raw reads report every parsed job with its posting age; the
            # 48-hour discovery window is applied by the discovery workflow
            # (discover-jobs) or requested explicitly via max_posted_hours.
            data = _filter_jobs_by_freshness(
                data,
                kwargs.get("max_posted_hours"),
                diagnostics=diagnostics,
            )
            return RuntimeResult(skill, data, diagnostics)
        elif skill == "people":
            data = await people.search(
                page,
                kwargs.get("query", "Power BI recruiter"),
                kwargs.get("location", ""),
            )
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
