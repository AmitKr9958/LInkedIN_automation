from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SelectorCheck:
    name: str
    found: bool
    detail: str = ""


async def check_page(page) -> list[SelectorCheck]:
    checks = [
        ("linkedin-domain", "linkedin.com" in (page.url or "").lower()),
        ("login-form", await page.locator("input[type='password']").count() > 0),
        ("main-content", await page.locator("main").count() > 0),
        ("job-card", await page.locator("li.jobs-search-results__list-item, .job-card-container").count() > 0),
        ("profile-heading", await page.locator("main h1, h1").count() > 0),
    ]
    return [SelectorCheck(name, found) for name, found in checks]
