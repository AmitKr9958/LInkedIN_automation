import asyncio

from app.browser import linkedin_browser
from app.config import settings

SELECTORS = [
    "li.jobs-search-results__list-item",
    "li.scaffold-layout__list-item",
    "[data-occludable-job-id]",
    ".job-card-container",
    "li:has(a[href*='/jobs/view/'])",
    "li:has(a[href*='/jobs/collections/'])",
    "[data-job-id]",
    "article:has(a[href*='/jobs/'])",
    "main a[href*='/jobs/']",
]

async def main():
    async with linkedin_browser() as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()

        await page.goto(
            f"{settings.linkedin_base_url}/jobs/search/?keywords=Power%20BI%20Developer&location=Gurgaon",
            wait_until="domcontentloaded",
            timeout=60_000,
        )
        await page.wait_for_timeout(5000)

        print("URL:", page.url)
        print("TITLE:", await page.title())

        for selector in SELECTORS:
            try:
                count = await page.locator(selector).count()
            except Exception:
                count = "ERROR"
            print(f"{count:>5}  {selector}")

        print("BODY_HEAD:")
        try:
            text = await page.locator("body").inner_text()
            print(" ".join(text.split())[:1500])
        except Exception as exc:
            print("body-read-error:", exc)

asyncio.run(main())
