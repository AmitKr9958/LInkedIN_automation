"""Temporary safe probe: trace companies.search internals on the live page.

Prints only element counts, public company URLs, page URLs, and trace lines.
Never reads or prints passwords, cookies, or session tokens.
"""

import asyncio

from app.browser import linkedin_browser
from app.linkedin_reader import current_session_state
from app.skills import companies


async def main():
    async with linkedin_browser() as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()
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
        print("session:", state.get("authenticated"), state.get("confidence"))

        legacy_orig = companies._legacy_search
        sdui_orig = companies._sdui_search

        async def traced_legacy(page):
            rows = await legacy_orig(page)
            print("  [trace] _legacy_search ->", len(rows))
            return rows

        async def traced_sdui(page):
            print("  [trace] _sdui_search entered, url:", page.url[:90])
            rows = await sdui_orig(page)
            print("  [trace] _sdui_search ->", len(rows))
            return rows

        companies._legacy_search = traced_legacy
        companies._sdui_search = traced_sdui
        try:
            results = await companies.search(page, "Power BI")
        finally:
            companies._legacy_search = legacy_orig
            companies._sdui_search = sdui_orig
        print("search results:", len(results))
        for company in results[:5]:
            print("  company:", company.name, "|", company.industry, "|", company.href[:70])

        direct = await companies._sdui_search(page)
        print("direct _sdui_search on settled page:", len(direct))
        for company in direct[:3]:
            print("  ", company.name, "|", company.industry, "|", company.href[:60])

        # Run the exact _sdui_search script on the settled page, with the
        # exception surfaced instead of swallowed.
        script = (
            "() => Array.from(document.querySelectorAll(\"main a[href*='/company/']\"))"
            ".slice(0, 200)"
            ".map(a => ({href: a.getAttribute('href') || '', text: a.innerText || ''}))"
        )
        try:
            rows = await page.evaluate(script)
            print("exact script rows:", len(rows or []))
            if rows:
                first = rows[0]
                print("  first href:", str(first.get("href"))[:80])
                print("  first text:", str(first.get("text"))[:80].replace("\n", " | "))
        except Exception as exc:
            print("exact script exception:", type(exc).__name__, ":", str(exc)[:300])


asyncio.run(main())
