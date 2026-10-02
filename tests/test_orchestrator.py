import app.orchestrator as orchestrator
from app.history import History


def test_discovery_report_logs_activity(monkeypatch, tmp_path):
    monkeypatch.setattr(
        orchestrator, "History", lambda: History(tmp_path / "history.sqlite3")
    )
    logged = []
    monkeypatch.setattr(
        orchestrator, "log_activity", lambda *args, **kwargs: logged.append(args)
    )
    report = orchestrator.build_discovery_report(
        [
            {
                "title": "Power BI Developer",
                "company": "Example",
                "location": "Gurgaon",
                "url": "https://www.linkedin.com/jobs/view/123/",
            }
        ]
    )
    assert report.ranked
    assert logged == [("discovery_run", "linkedin_jobs", "ok", "ranked=1 new=1 removed_stale=0 freshness_hours=6")]

def test_discovery_cleanup_runs_after_upsert_and_excludes_stale_candidates(monkeypatch, tmp_path):
    from app.history import History

    history_path = tmp_path / "history.sqlite3"
    history = History(history_path)
    history.upsert_job(
        {
            "title": "Old existing job",
            "company": "Old Co",
            "location": "Gurgaon",
            "url": "https://www.linkedin.com/jobs/view/old/",
            "posted_hours": 20,
            "posted_text": "20 hours ago",
        },
        80,
        ["old"],
    )

    monkeypatch.setattr(orchestrator, "History", lambda: History(history_path))
    monkeypatch.setattr(orchestrator, "log_activity", lambda *args, **kwargs: None)

    report = orchestrator.build_discovery_report(
        [
            {
                "title": "Fresh BI Developer",
                "company": "Fresh Co",
                "location": "Gurgaon",
                "url": "https://www.linkedin.com/jobs/view/fresh/",
                "posted_hours": 2,
                "posted_text": "2 hours ago",
            },
            {
                "title": "Stale BI Developer",
                "company": "Stale Co",
                "location": "Gurgaon",
                "url": "https://www.linkedin.com/jobs/view/stale/",
                "posted_hours": 12,
                "posted_text": "12 hours ago",
            },
        ],
        freshness_hours=6,
    )

    urls = {item["job"]["url"] for item in report.ranked}
    assert urls == {"https://www.linkedin.com/jobs/view/fresh/"}
    assert report.removed_stale >= 2

    remaining = History(history_path).recent(20)
    remaining_urls = {row[3] for row in remaining}
    assert remaining_urls == {"https://www.linkedin.com/jobs/view/fresh/"}


def test_discovery_cleanup_removes_unknown_age_candidates(monkeypatch, tmp_path):
    from app.history import History

    history_path = tmp_path / "history.sqlite3"
    monkeypatch.setattr(orchestrator, "History", lambda: History(history_path))
    monkeypatch.setattr(orchestrator, "log_activity", lambda *args, **kwargs: None)

    report = orchestrator.build_discovery_report(
        [
            {
                "title": "Unknown Age Job",
                "company": "Unknown Co",
                "location": "Gurgaon",
                "url": "https://www.linkedin.com/jobs/view/unknown/",
            }
        ],
        freshness_hours=6,
    )

    assert report.ranked == []
    assert History(history_path).recent(20) == []
