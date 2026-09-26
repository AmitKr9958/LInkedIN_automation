from types import SimpleNamespace

from app import daily_agent


class FakeTracker:
    def __init__(self):
        self.added = []

    def add(self, url, title="", company="", status="new"):
        self.added.append((url, title, company, status))


def test_build_agent_report_tracks_top_jobs_and_drafts_recruiter(monkeypatch):
    class FakeTarget:
        def to_dict(self):
            return {"name": "Recruiter", "profile_url": "https://linkedin.test/p/1"}

    ranked = [
        {
            "job": {
                "title": "Power BI Developer",
                "company": "Example",
                "location": "Gurgaon, India",
                "url": "https://linkedin.test/jobs/1",
            },
            "score": 90,
            "reasons": ["target role keyword"],
        }
    ]

    monkeypatch.setattr(
        daily_agent,
        "build_discovery_report",
        lambda rows: SimpleNamespace(ranked=ranked, new_count=1),
    )
    monkeypatch.setattr(daily_agent, "build_outreach_plan", lambda people, job: [FakeTarget()])
    monkeypatch.setattr(
        daily_agent,
        "draft_connection",
        lambda target, role, skills: {"target": target.to_dict(), "note": "draft"},
    )

    report = daily_agent.build_agent_report(
        [[{
            "title": "Power BI Developer",
            "company": "Example",
            "location": "Gurgaon, India",
            "url": "https://linkedin.test/jobs/1",
        }]],
        people=[object()],
        tracker=FakeTracker(),
    )

    assert report.jobs_found == 1
    assert report.new_jobs == 1
    assert report.tracked_jobs == 1
    assert len(report.recruiter_targets) == 1
    assert len(report.connection_drafts) == 1


def test_run_agent_once_uses_all_requested_locations():
    calls = []

    async def fake_read(skill, **kwargs):
        calls.append((skill, kwargs))
        if skill == "jobs":
            return SimpleNamespace(
                data=[],
                diagnostics={"final_returned": 0},
            )
        return SimpleNamespace(data=[])

    report = __import__("asyncio").run(
        daily_agent.run_agent_once(
            locations=["Delhi", "Gurgaon"],
            read_fn=fake_read,
            tracker=FakeTracker(),
        )
    )

    assert report.jobs_found == 0
    assert [call[1]["location"] for call in calls if call[0] == "jobs"] == [
        "Delhi",
        "Gurgaon",
    ]


def test_build_agent_report_handles_normalized_people_dicts(monkeypatch):
    from app.outreach import build_outreach_plan

    people = [
        {
            "name": "Priya Recruiter",
            "headline": "Technical Recruiter - Data & Analytics",
            "location": "Gurgaon, India",
            "href": "https://linkedin.test/in/priya",
            "text": "Technical Recruiter - Data & Analytics",
        }
    ]
    job = {
        "title": "Power BI Developer",
        "company": "Example",
        "url": "https://linkedin.test/jobs/1",
    }

    targets = build_outreach_plan(people, job)

    assert len(targets) == 1
    assert targets[0].name == "Priya Recruiter"
    assert targets[0].target_type == "recruiter"
    assert targets[0].profile_url.endswith("/priya")
    assert targets[0].job_url.endswith("/1")
