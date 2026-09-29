from app.dashboard import _HTML, _task_get, _task_submit


def test_dashboard_has_control_center_sections():
    for marker in [
        "Skill Center",
        "Job Intelligence",
        "Application Pipeline",
        "Approval Queue",
        "Agent Runs",
        "/api/tasks/",
        "Run Agent",
        "Recent activity",
        "/api/applications/transition",
        "transitionApplication",
        "COMMAND CENTER",
        "READ-ONLY · 2H CADENCE",
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
