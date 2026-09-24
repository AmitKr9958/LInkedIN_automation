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
    assert logged == [("discovery_run", "linkedin_jobs", "ok", "ranked=1 new=1")]
