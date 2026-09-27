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


def test_run_agent_once_retries_transient_location_failure():
    calls = []
    async def flaky_read(skill, **kwargs):
        if skill == "jobs":
            calls.append(kwargs.get("location"))
        if len([x for x in calls if x == "Delhi"]) == 1:
            raise TimeoutError("temporary browser timeout")
        return SimpleNamespace(data=[], diagnostics={"final_returned": 0})

    report = __import__("asyncio").run(
        daily_agent.run_agent_once(
            locations=["Delhi"],
            read_fn=flaky_read,
            tracker=FakeTracker(),
        )
    )

    assert report.jobs_found == 0
    assert calls == ["Delhi", "Delhi"]


def test_run_agent_once_fails_closed_on_chromium_missing():
    """Infrastructure browser failures must not report as successful empty cycles."""
    async def broken_read(skill, **kwargs):
        raise RuntimeError(
            "Chromium is not installed. Close other agent/Chromium instances "
            "using this profile or run 'python -m playwright install chromium'."
        )

    try:
        __import__("asyncio").run(
            daily_agent.run_agent_once(
                locations=["Delhi", "Gurgaon"],
                read_fn=broken_read,
                tracker=FakeTracker(),
            )
        )
        raised = False
    except RuntimeError as exc:
        raised = True
        assert "infrastructure failure" in str(exc).lower() or "chromium" in str(exc).lower()
    assert raised, "expected infrastructure failure to fail closed"


def test_run_agent_once_fails_closed_on_auth_failure():
    async def unauth_read(skill, **kwargs):
        raise RuntimeError(
            "LinkedIn session is not verified. Run 'python -m app login' "
            "with HEADLESS=false and sign in manually."
        )

    try:
        __import__("asyncio").run(
            daily_agent.run_agent_once(
                locations=["Delhi"],
                read_fn=unauth_read,
                tracker=FakeTracker(),
            )
        )
        raised = False
    except RuntimeError as exc:
        raised = True
        assert "session is not verified" in str(exc).lower()
    assert raised


def test_build_agent_report_ranks_hiring_posts():
    report = daily_agent.build_agent_report(
        [[]],
        tracker=FakeTracker(),
        post_batches=[[
            {
                "author": "Hiring Manager",
                "text": "We are hiring a Power BI Developer in Gurgaon. Apply now!",
                "profile_url": "https://linkedin.test/in/hiring-manager",
            },
            {
                "author": "Unrelated",
                "text": "We are hiring a Finance Manager in Delhi.",
                "profile_url": "https://linkedin.test/in/unrelated",
            },
        ]],
    )

    assert len(report.hiring_posts) == 1
    assert report.hiring_posts[0]["post"]["author"] == "Hiring Manager"
    assert report.hiring_posts[0]["score"] >= 60
    assert report.hiring_post_targets[0]["target"]["name"] == "Hiring Manager"


def test_run_agent_once_scans_hiring_posts():
    calls = []

    async def fake_read(skill, **kwargs):
        calls.append((skill, kwargs))
        if skill == "jobs":
            return SimpleNamespace(data=[], diagnostics={"final_returned": 0})
        if skill == "posts":
            return SimpleNamespace(data=[{
                "author": "Recruiter",
                "text": "Looking for a Data Analyst in Noida. Applications open.",
                "href": "https://linkedin.test/in/recruiter",
            }])
        return SimpleNamespace(data=[])

    report = __import__("asyncio").run(
        daily_agent.run_agent_once(
            locations=["Noida"],
            read_fn=fake_read,
            tracker=FakeTracker(),
        )
    )

    assert any(skill == "posts" for skill, _ in calls)
    assert report.hiring_posts
    assert report.hiring_post_targets[0]["target"]["name"] == "Recruiter"
    assert report.diagnostics["post_scan_queries"] > 0



def test_run_agent_once_scans_personalized_feed_with_48_hour_window():
    calls = []

    async def fake_read(skill, **kwargs):
        calls.append((skill, kwargs))
        if skill == "jobs":
            return SimpleNamespace(data=[], diagnostics={"final_returned": 0})
        if skill == "posts" and kwargs.get("feed"):
            return SimpleNamespace(data=[{
                "author": "Feed Recruiter",
                "text": "We are hiring a Senior Power BI Developer in Gurgaon. 1 day ago",
                "href": "https://linkedin.test/in/feed-recruiter",
            }])
        return SimpleNamespace(data=[])

    report = __import__("asyncio").run(
        daily_agent.run_agent_once(
            locations=["Gurgaon"],
            read_fn=fake_read,
            tracker=FakeTracker(),
        )
    )

    feed_calls = [kwargs for skill, kwargs in calls if skill == "posts" and kwargs.get("feed")]
    assert feed_calls
    assert feed_calls[0]["max_posted_hours"] == 48
    assert feed_calls[0]["max_scrolls"] == 8
    assert report.diagnostics["feed_scan_enabled"] is True
