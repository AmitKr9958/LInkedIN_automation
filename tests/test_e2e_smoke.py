import pytest
from playwright.sync_api import Page, expect

@pytest.mark.e2e
def test_browser_smoke(page: Page):
    page.goto("https://example.com")
    expect(page).to_have_title("Example Domain")
