import pytest

from app.scrolling import scroll_page_completely


class FakePage:
    def __init__(self, states):
        self.states = iter(states)
        self.calls = 0

    async def evaluate(self, script):
        self.calls += 1
        return next(self.states)


    async def wait_for_timeout(self, _ms):
        return None


@pytest.mark.asyncio
async def test_complete_scroll_stops_after_stable_geometry():
    page = FakePage([
        {"height": 1000, "top": 1000, "containers": 1, "moved": 1},
        {"height": 1200, "top": 1200, "containers": 1, "moved": 1},
        {"height": 1200, "top": 1200, "containers": 1, "moved": 0},
        {"height": 1200, "top": 1200, "containers": 1, "moved": 0},
    ])
    rounds = await scroll_page_completely(page, max_rounds=10, pause_ms=0)
    assert rounds == 4
    assert page.calls == 4


@pytest.mark.asyncio
async def test_complete_scroll_is_bounded():
    page = FakePage([
        {"height": i + 1, "top": i + 1, "containers": 1, "moved": 1}
        for i in range(20)
    ])
    rounds = await scroll_page_completely(page, max_rounds=5, pause_ms=0)
    assert rounds == 5
    assert page.calls == 5
