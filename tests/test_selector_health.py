import pytest

from app.selector_health import check_page


@pytest.mark.asyncio
async def test_selector_health():
    class Locator:
        def __init__(self, count): self._count = count
        async def count(self): return self._count

    class Page:
        url = "https://www.linkedin.com/feed/"
        def locator(self, selector):
            return Locator(1 if selector != "input[type='password']" else 0)

    checks = await check_page(Page())
    assert any(x.name == "linkedin-domain" and x.found for x in checks)
