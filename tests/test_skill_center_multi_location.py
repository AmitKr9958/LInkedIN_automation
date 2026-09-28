import asyncio

from app.skill_runtime import RuntimeResult
import app.skill_center as skill_center


class _FakeBrowser:
    def __init__(self, page):
        self.pages = [page]

    async def __aenter__(self):
        _FakeBrowser.entered += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        _FakeBrowser.exited += 1


class _Page:
    pass


def test_multi_location_read_reuses_one_browser_session(monkeypatch):
    calls = []
    page = _Page()
    _FakeBrowser.entered = 0
    _FakeBrowser.exited = 0

    async def fake_auth(_page):
        return {"authenticated": True, "confidence": "high"}

    async def fake_read(_page, skill, **kwargs):
        calls.append((skill, kwargs["location"]))
        return RuntimeResult(
            skill=skill,
            data=[{"href": f"https://example.test/{kwargs['location']}"}],
            diagnostics={"location": kwargs["location"]},
        )

    monkeypatch.setattr(skill_center, "linkedin_browser", lambda: _FakeBrowser(page))
    monkeypatch.setattr(skill_center, "ensure_authenticated", fake_auth)
    monkeypatch.setattr(skill_center, "run_read_on_page", fake_read)

    result = asyncio.run(
        skill_center.run_skill(
            "jobs",
            {
                "query": "Power BI",
                "location": "Gurgaon/Gurugram, Noida",
                "max_posted_hours": 48,
            },
        )
    )

    assert _FakeBrowser.entered == 1
    assert _FakeBrowser.exited == 1
    assert calls == [("jobs", "Gurgaon/Gurugram"), ("jobs", "Noida")]
    assert result["diagnostics"]["session_reused"] is True
    assert len(result["data"]) == 2
