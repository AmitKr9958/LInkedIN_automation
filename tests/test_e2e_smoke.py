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


@pytest.mark.e2e
async def test_dashboard_browser_smoke():
    import threading
    from http.server import ThreadingHTTPServer
    from app.dashboard import _Handler

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            try:
                page = await browser.new_page(viewport={"width": 1440, "height": 900})
                errors = []
                page.on("pageerror", lambda exc: errors.append(str(exc)))
                await page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
                await page.locator('button[data-view="jobs"]').click()
                assert await page.locator("#jobStatusFilter").count() == 1
                assert await page.locator("#jobWorkplaceFilter").count() == 1
                assert await page.locator("#jobScoreSort").count() == 1
                await page.locator("#jobStatusFilter").select_option("new")
                await page.locator("#jobScoreSort").select_option("asc")
                await page.locator('button[data-view="approvals"]').click()
                assert await page.locator("#approvalCards").count() == 1
                await page.locator('button[data-view="agent"]').click()
                assert await page.locator("#tasks").count() == 1
                assert not errors, f"dashboard JavaScript errors: {errors}"
            finally:
                await browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
