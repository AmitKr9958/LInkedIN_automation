from app.dashboard import _HTML, _task_get, _task_submit


def test_dashboard_has_control_center_sections():
    for marker in [
        "Skill Center",
        "Job Intelligence",
        "Application Workspace",
        "Approval Queue",
        "Agent Runs",
        "/api/tasks/",
        "Run Agent",
        "Recent activity",
        "/api/applications/transition",
        "transitionApplication",
        "COMMAND CENTER",
        "READ-ONLY · 30M CADENCE",
        "6H FRESHNESS",
        "posted within the last 6 hours",
        "Stale removed",
        "result-shell",
        "run-summary",
        "live-pill",
        "Relevant jobs",
        "Open ↗",
        "result-cards",
        "result-card",
        "result-message",
        "result-fields",
        "result-subhead",
        "approval-empty",
        "approval-card",
        "approval-flow",
        "Your approval is required.",
        "Proposed action",
        "Pending approvals",
        "Review before LinkedIn actions",
        "GOVERNANCE GATE",
        "agent-result",
        "agent-summary-grid",
        "agent-section",
        "Technical diagnostics",
        "No LinkedIn account actions were performed",
        "scrollbar-gutter:stable",
        ".main::-webkit-scrollbar",
        "Application Workspace",
        "Career pipeline",
        "applicationMetrics",
        "appStatusFilter",
        "appSearch",
        "saveApplicationDetails",
        "Track application",
        "Tracked",
        "state.summary?.applications",
        "/api/applications/add",
        "/api/applications/details",
        "Recruiter",
        "Resume version",
        "Next follow-up",
        "Interview date",
        "Salary / CTC notes",
    ]:
        assert marker in _HTML


def test_dashboard_task_runner_returns_immediately_and_completes():
    task_id = _task_submit("test", lambda: {"ok": True})
    assert task_id
    import time
    deadline = time.time() + 2
    while time.time() < deadline:
        task = _task_get(task_id)
        if task and task.get("status") == "completed":
            assert task["result"] == {"ok": True}
            return
        time.sleep(0.01)
    raise AssertionError("background dashboard task did not complete")


def test_dashboard_exposes_transition_constraints_and_empty_job_state():
    import inspect
    import app.dashboard as dashboard

    assert "allowed_transitions" in inspect.getsource(dashboard._summary)
    assert "X-Content-Type-Options" in inspect.getsource(dashboard._Handler._send)
    assert "No jobs stored yet." in _HTML


def test_dashboard_jobs_intelligence_controls():
    for marker in [
        "jobSearch",
        "jobStatusFilter",
        "jobWorkplaceFilter",
        'target="_blank"',
        'rel="noopener noreferrer"',
        "Workplace",
        "Score",
        "filterJobs",
        "jobScoreSort",
        "normalizeFilterValue",
        "Score: High → Low",
        "Score: Low → High",
        "Score ↕",
    ]:
        assert marker in _HTML


def test_dashboard_summary_can_build_application_transition_metadata(monkeypatch, tmp_path):
    import sqlite3
    import app.dashboard as dashboard

    db_path = tmp_path / "data" / "activity.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "CREATE TABLE applications(job_url TEXT PRIMARY KEY,title TEXT,company TEXT,status TEXT NOT NULL,updated_at TEXT NOT NULL,notes TEXT DEFAULT '')"
        )
        db.execute(
            "CREATE TABLE job_history(id INTEGER PRIMARY KEY,title TEXT,company TEXT,location TEXT,url TEXT,score REAL,reasons TEXT,status TEXT,first_seen TEXT)"
        )
        db.execute(
            "CREATE TABLE approval_queue(id TEXT PRIMARY KEY,action TEXT,target TEXT,payload TEXT,status TEXT,created_at TEXT)"
        )
        db.commit()

    monkeypatch.setattr(dashboard, "ROOT", tmp_path)
    summary = dashboard._summary()
    assert summary["application_count"] == 0
    assert summary["applications"] == []
    assert summary["warnings"] == []


def test_dashboard_rejects_non_boolean_approval_decisions():
    import app.dashboard as dashboard

    assert dashboard._parse_approval_decision(True) is True
    assert dashboard._parse_approval_decision(False) is False
    import pytest
    with pytest.raises(ValueError):
        dashboard._parse_approval_decision("false")


def test_dashboard_prevents_duplicate_active_agent_runs():
    import app.dashboard as dashboard

    dashboard._TASKS.clear()
    with dashboard._TASK_LOCK:
        dashboard._TASKS["active-agent"] = {
            "id": "active-agent",
            "kind": "agent",
            "status": "running",
        }
    assert dashboard._has_active_task("agent") is True
    assert dashboard._has_active_task("skill:jobs") is False
    dashboard._TASKS.clear()


def test_dashboard_body_size_limit_is_defined():
    import app.dashboard as dashboard

    assert dashboard._MAX_REQUEST_BODY_BYTES == 1_048_576


def test_dashboard_hides_raw_overview_and_system_json_by_default():
    assert 'id="lastRun"></pre>' not in _HTML
    assert 'id="systemDetails"></pre>' not in _HTML
    assert "System health" in _HTML
    assert "Technical diagnostics" in _HTML


def test_dashboard_manual_agent_uses_six_hour_freshness_window():
    import inspect
    import app.dashboard as dashboard

    source = inspect.getsource(dashboard._Handler.do_POST)
    assert "run_agent_once(max_posted_hours=6)" in source

def test_dashboard_track_application_marks_already_tracked_jobs():
    assert "state.summary?.applications" in _HTML
    assert "const isTracked=tracked.has" in _HTML
    assert '<button class="btn" disabled>Tracked</button>' in _HTML

def test_dashboard_application_actions_use_responsive_action_group():
    assert "application-actions" in _HTML
    assert "table-layout:fixed" in _HTML
    assert "application-table th:nth-child(8)" in _HTML


def test_dashboard_summary_filters_stale_jobs_with_posting_metadata(monkeypatch, tmp_path):
    import sqlite3
    from datetime import datetime, timedelta, timezone
    import app.dashboard as dashboard

    now = datetime.now(timezone.utc)
    fresh_posted_at = (now - timedelta(hours=2)).isoformat()
    fresh_first_seen = (now - timedelta(hours=1)).isoformat()
    old_posted_at = (now - timedelta(hours=20)).isoformat()
    old_first_seen = (now - timedelta(hours=19)).isoformat()

    db_path = tmp_path / "data" / "activity.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        db.execute(
            """CREATE TABLE job_history(
                id INTEGER PRIMARY KEY,
                title TEXT, company TEXT, location TEXT, url TEXT,
                score REAL, reasons TEXT, status TEXT, first_seen TEXT,
                posted_hours REAL, posted_text TEXT, posted_at TEXT
            )"""
        )
        db.execute(
            "INSERT INTO job_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (1, "Fresh BI Analyst", "Fresh Co", "Gurugram, Haryana, India", "fresh", 90, "fresh", "new", fresh_first_seen, 2, "2 hours ago", fresh_posted_at),
        )
        db.execute(
            "INSERT INTO job_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (2, "Old BI Analyst", "Old Co", "Gurugram, Haryana, India", "old", 90, "old", "new", old_first_seen, 20, "20 hours ago", old_posted_at),
        )
        db.commit()

    monkeypatch.setattr(dashboard, "ROOT", tmp_path)
    summary = dashboard._summary()
    assert summary["jobs_tracked"] == 1
    assert [job["title"] for job in summary["jobs"]] == ["Fresh BI Analyst"]


def test_dashboard_excludes_unknown_posting_age(monkeypatch, tmp_path):
    import sqlite3
    import app.dashboard as dashboard

    db_path = tmp_path / "data" / "activity.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute(
            """CREATE TABLE job_history(
                id INTEGER PRIMARY KEY,
                title TEXT, company TEXT, location TEXT, url TEXT,
                score REAL, reasons TEXT, status TEXT, first_seen TEXT,
                posted_hours REAL, posted_text TEXT, posted_at TEXT
            )"""
        )
        db.execute(
            "INSERT INTO job_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (1, "Unknown BI Analyst", "Unknown Co", "Delhi, India", "unknown", 90, "unknown", "new", "2026-10-01T08:00:00+00:00", None, "", None),
        )
        db.commit()

    monkeypatch.setattr(dashboard, "ROOT", tmp_path)
    summary = dashboard._summary()
    assert summary["jobs_tracked"] == 0
    assert summary["jobs"] == []

def test_dashboard_uses_30_minute_cadence_and_clear_empty_application_values():
    assert "READ-ONLY · 30M CADENCE · 6H FRESHNESS" in _HTML
    assert "function displayApplicationValue(value)" in _HTML
    assert "displayApplicationValue(x.applied_at)" in _HTML
    assert "displayApplicationValue(x.next_follow_up)" in _HTML
    assert "displayApplicationValue(x.recruiter)" in _HTML


def test_dashboard_db_reader_uses_short_busy_timeout():
    import inspect
    import app.dashboard as dashboard

    source = inspect.getsource(dashboard._db)
    assert "timeout=0.5" in source
    assert "busy_timeout=500" in source


def test_dashboard_summary_does_not_run_history_migration(monkeypatch, tmp_path):
    import sqlite3
    import app.dashboard as dashboard

    db_path = tmp_path / "data" / "activity.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "CREATE TABLE job_history(id INTEGER PRIMARY KEY, title TEXT, company TEXT, location TEXT, url TEXT, score REAL, reasons TEXT, status TEXT, first_seen TEXT, posted_hours REAL, posted_text TEXT, posted_at TEXT)"
        )
        db.commit()

    monkeypatch.setattr(dashboard, "ROOT", tmp_path)
    dashboard._summary()

def test_dashboard_application_workspace_hides_stale_jobs_without_deleting_records(monkeypatch, tmp_path):
    import sqlite3
    from datetime import datetime, timedelta, timezone
    import app.dashboard as dashboard

    now = datetime.now(timezone.utc)
    fresh = (now - timedelta(hours=2)).isoformat()
    stale = (now - timedelta(hours=20)).isoformat()

    db_path = tmp_path / "data" / "activity.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute(
            """CREATE TABLE applications(
                job_url TEXT PRIMARY KEY, title TEXT, company TEXT, status TEXT NOT NULL,
                updated_at TEXT NOT NULL, notes TEXT DEFAULT '', discovered_at TEXT,
                applied_at TEXT, source TEXT DEFAULT '', location TEXT DEFAULT '',
                recruiter TEXT DEFAULT '', resume_version TEXT DEFAULT '',
                next_follow_up TEXT DEFAULT '', interview_date TEXT DEFAULT '',
                salary_notes TEXT DEFAULT ''
            )"""
        )
        db.execute(
            """CREATE TABLE job_history(
                id INTEGER PRIMARY KEY, title TEXT, company TEXT, location TEXT, url TEXT,
                score REAL, reasons TEXT, status TEXT, first_seen TEXT,
                posted_hours REAL, posted_text TEXT, posted_at TEXT
            )"""
        )
        db.execute(
            "INSERT INTO applications(job_url,title,company,status,updated_at,discovered_at) VALUES(?,?,?,?,?,?)",
            ("fresh-url", "Fresh Application", "Fresh Co", "new", fresh, fresh),
        )
        db.execute(
            "INSERT INTO applications(job_url,title,company,status,updated_at,discovered_at) VALUES(?,?,?,?,?,?)",
            ("stale-url", "Stale Application", "Stale Co", "new", stale, stale),
        )
        db.execute(
            "INSERT INTO job_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (1, "Fresh Application", "Fresh Co", "Delhi, India", "fresh-url", 90, "fresh", "new", fresh, 2, "2 hours ago", fresh),
        )
        db.commit()

    monkeypatch.setattr(dashboard, "ROOT", tmp_path)
    summary = dashboard._summary()

    assert summary["application_count"] == 1
    assert [item["title"] for item in summary["applications"]] == ["Fresh Application"]

    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 2

def test_dashboard_applications_filter_stale_posting_age_without_deleting_records(monkeypatch, tmp_path):
    import sqlite3
    from datetime import datetime, timedelta, timezone
    import app.dashboard as dashboard

    now = datetime.now(timezone.utc)
    fresh_posted_at = (now - timedelta(hours=2)).isoformat()
    old_posted_at = (now - timedelta(hours=20)).isoformat()
    first_seen = (now - timedelta(hours=1)).isoformat()

    db_path = tmp_path / "data" / "activity.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        db.execute(
            """CREATE TABLE applications(
                job_url TEXT PRIMARY KEY, title TEXT, company TEXT, status TEXT,
                updated_at TEXT, notes TEXT, discovered_at TEXT, applied_at TEXT,
                source TEXT, location TEXT, recruiter TEXT, resume_version TEXT,
                next_follow_up TEXT, interview_date TEXT, salary_notes TEXT
            )"""
        )
        db.execute(
            """CREATE TABLE job_history(
                id INTEGER PRIMARY KEY, title TEXT, company TEXT, location TEXT,
                url TEXT, score REAL, reasons TEXT, status TEXT, first_seen TEXT,
                posted_hours REAL, posted_text TEXT, posted_at TEXT
            )"""
        )
        db.execute(
            "INSERT INTO applications VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("fresh", "Fresh BI", "Fresh Co", "new", now.isoformat(), "", first_seen, "", "", "Gurgaon", "", "", "", "", ""),
        )
        db.execute(
            "INSERT INTO applications VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("old", "Old BI", "Old Co", "new", now.isoformat(), "", first_seen, "", "", "Gurgaon", "", "", "", "", ""),
        )
        db.execute(
            "INSERT INTO job_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (1, "Fresh BI", "Fresh Co", "Gurgaon", "fresh", 80, "fresh", "new", first_seen, 2, "2 hours ago", fresh_posted_at),
        )
        db.execute(
            "INSERT INTO job_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (2, "Old BI", "Old Co", "Gurgaon", "old", 80, "old", "new", first_seen, 20, "20 hours ago", old_posted_at),
        )
        db.commit()

    monkeypatch.setattr(dashboard, "ROOT", tmp_path)
    summary = dashboard._summary()

    assert summary["application_count"] == 1
    assert [item["title"] for item in summary["applications"]] == ["Fresh BI"]

    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 2


def test_dashboard_applications_exclude_unknown_age(monkeypatch, tmp_path):
    import sqlite3
    import app.dashboard as dashboard

    db_path = tmp_path / "data" / "activity.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute(
            """CREATE TABLE applications(
                job_url TEXT PRIMARY KEY, title TEXT, company TEXT, status TEXT,
                updated_at TEXT, notes TEXT, discovered_at TEXT
            )"""
        )
        db.execute(
            "INSERT INTO applications VALUES(?,?,?,?,?,?,?)",
            ("unknown", "Unknown BI", "Unknown Co", "new", "not-a-date", "", "not-a-date"),
        )
        db.execute(
            """CREATE TABLE job_history(
                id INTEGER PRIMARY KEY, title TEXT, company TEXT, location TEXT,
                url TEXT, score REAL, reasons TEXT, status TEXT, first_seen TEXT,
                posted_hours REAL, posted_text TEXT, posted_at TEXT
            )"""
        )
        db.commit()

    monkeypatch.setattr(dashboard, "ROOT", tmp_path)
    summary = dashboard._summary()
    assert summary["application_count"] == 0
    assert summary["applications"] == []
