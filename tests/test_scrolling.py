import pytest

from app.scrolling import scroll_and_capture, scroll_page_completely


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


@pytest.mark.asyncio
async def test_incremental_capture_keeps_virtualized_records():
    page = FakePage([
        {"height": 1000, "top": 500, "viewport": 500, "moved": 1, "atEnd": False},
        {"height": 1400, "top": 900, "viewport": 500, "moved": 1, "atEnd": False},
        {"height": 1600, "top": 1100, "viewport": 500, "moved": 1, "atEnd": True},
        {"height": 1600, "top": 1100, "viewport": 500, "moved": 0, "atEnd": True},
    ])

    batches = iter([
        [{"href": "/jobs/view/1"}, {"href": "/jobs/view/2"}],
        [{"href": "/jobs/view/2"}, {"href": "/jobs/view/3"}],
        [{"href": "/jobs/view/3"}, {"href": "/jobs/view/4"}],
        [{"href": "/jobs/view/4"}],
    ])

    async def capture():
        return next(batches)

    records, rounds = await scroll_and_capture(page, capture, max_rounds=6, pause_ms=0)
    assert rounds == 3
    assert [item["href"] for item in records] == [
        "/jobs/view/1", "/jobs/view/2", "/jobs/view/3", "/jobs/view/4"
    ]


@pytest.mark.asyncio
async def test_incremental_capture_is_bounded():
    page = FakePage([
        {"height": i + 1, "top": i + 1, "viewport": 500, "moved": 1, "atEnd": False}
        for i in range(20)
    ])

    async def capture():
        return [{"href": "/jobs/view/1"}]

    records, rounds = await scroll_and_capture(page, capture, max_rounds=5, pause_ms=0)
    assert rounds == 5
    assert len(records) == 1
