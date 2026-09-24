import pytest
from playwright.async_api import async_playwright


@pytest.mark.e2e
async def test_browser_smoke():
    # Self-contained async Playwright usage: the sync API keeps a session-wide
    # event loop running, which breaks pytest-asyncio tests later in the suite.
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            page = await browser.new_page()
            await page.goto("https://example.com")
            assert await page.title() == "Example Domain"
        finally:
            await browser.close()
