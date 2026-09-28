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
