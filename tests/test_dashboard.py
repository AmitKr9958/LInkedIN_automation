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
        "X-Content-Type-Options",
        "COMMAND CENTER",
        "READ-ONLY · 2H CADENCE",
        "result-shell",
        "run-summary",
        "live-pill",
        "Relevant jobs",
        "Open job ↗",
        "result-list",
        "result-cards",
        "result-card",
        "result-message",
        "result-fields",
        "result-subhead",
        "agent-result",
        "agent-summary-grid",
        "agent-section",
        "Technical diagnostics",
        "No LinkedIn account actions were performed",
        "Relevant jobs",

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
    assert "allowed_transitions" in __import__("app.dashboard", fromlist=["_summary"]).__dict__["_summary"].__code__.co_consts
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
        "Score: High → Low",
        "Score: Low → High",
        "Score ↕",
    ]:
        assert marker in _HTML
