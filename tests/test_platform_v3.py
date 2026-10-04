from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.platform.api import create_control_plane
from app.platform.models import AgentRunResult, RunState
from app.platform.run_repository import RunRepository


def test_run_repository_persists_and_lists_runs(tmp_path):
    repo = RunRepository(tmp_path / "platform.sqlite3")
    started = datetime.now(timezone.utc)
    repo.start("run-1", started, {"source": "test"})
    result = AgentRunResult(
        run_id="run-1",
        state=RunState.SUCCEEDED,
        started_at=started,
        finished_at=started,
        duration_seconds=1.25,
        jobs_found=4,
        new_jobs=2,
        metadata={"source": "test"},
    )
    repo.finish(result)

    assert repo.latest().run_id == "run-1"
    assert repo.latest().jobs_found == 4
    assert repo.list(10)[0].state == RunState.SUCCEEDED


def test_control_plane_health_and_runs(tmp_path):
    repo = RunRepository(tmp_path / "platform.sqlite3")
    app = create_control_plane(repo)
    client = TestClient(app)

    assert client.get("/api/v3/health").status_code == 200
    assert client.get("/api/v3/runs").json()["runs"] == []


def test_control_plane_latest_returns_404_without_runs(tmp_path):
    client = TestClient(create_control_plane(RunRepository(tmp_path / "platform.sqlite3")))
    assert client.get("/api/v3/runs/latest").status_code == 404


def test_task_repository_persists_lifecycle(tmp_path):
    from app.platform.task_repository import TaskRepository

    repo = TaskRepository(tmp_path / "platform.sqlite3")
    repo.create("task-1", "agent")
    repo.mark_running("task-1")
    repo.mark_completed("task-1", {"run_id": "run-1", "ok": True})

    item = repo.get("task-1")
    assert item["status"] == "completed"
    assert item["result"]["run_id"] == "run-1"
    assert repo.list(10)[0]["id"] == "task-1"


def test_task_repository_detects_active_work(tmp_path):
    from app.platform.task_repository import TaskRepository

    repo = TaskRepository(tmp_path / "platform.sqlite3")
    repo.create("task-2", "agent")
    assert repo.has_active("agent") is True


def test_control_plane_lists_durable_tasks(tmp_path):
    from app.platform.task_repository import TaskRepository

    path = tmp_path / "platform.sqlite3"
    repo = RunRepository(path)
    tasks = TaskRepository(path)
    tasks.create("task-3", "agent")

    client = TestClient(create_control_plane(repo))
    response = client.get("/api/v3/tasks?limit=10")

    assert response.status_code == 200
    assert response.json()["tasks"][0]["id"] == "task-3"


def test_task_repository_prune_keeps_active_tasks(tmp_path):
    from app.platform.task_repository import TaskRepository

    repo = TaskRepository(tmp_path / "platform.sqlite3")
    for index in range(55):
        task_id = f"done-{index}"
        repo.create(task_id, "agent")
        repo.mark_completed(task_id, {"index": index})
    repo.create("active", "agent")
    repo.mark_running("active")

    repo.prune(50)

    assert repo.get("active") is not None
    assert len(repo.list(100)) == 51


def test_notification_outbox_is_durable_and_idempotent(tmp_path):
    from app.platform.notification_repository import NotificationRepository

    repo = NotificationRepository(tmp_path / "platform.sqlite3")
    repo.enqueue("n-1", "agent-run:r-1:completion", "telegram", "hello")
    repo.enqueue("n-1-duplicate", "agent-run:r-1:completion", "telegram", "hello again")

    pending = repo.pending()
    assert len(pending) == 1
    assert pending[0]["message"] == "hello"

    calls = []

    def sender(message):
        calls.append(message)
        return True, "sent"

    assert repo.deliver_pending(sender) == 1
    assert calls == ["hello"]
    assert repo.pending() == []
    assert repo.get("n-1")["status"] == "sent"


def test_notification_outbox_retains_failures_for_retry(tmp_path):
    from app.platform.notification_repository import NotificationRepository

    repo = NotificationRepository(tmp_path / "platform.sqlite3")
    repo.enqueue("n-2", "agent-run:r-2:completion", "telegram", "retry me")

    assert repo.deliver_pending(lambda message: (False, "network down")) == 0
    item = repo.get("n-2")
    assert item["status"] == "pending"
    assert item["attempts"] == 1
    assert item["last_error"] == "network down"


def test_control_plane_rejects_invalid_agent_task_request(tmp_path):
    client = TestClient(create_control_plane(RunRepository(tmp_path / "platform.sqlite3")))
    response = client.post(
        "/api/v3/tasks/agent",
        json={"max_posted_hours": 0},
    )
    assert response.status_code == 422


def test_control_task_service_submits_and_persists_result(tmp_path):
    from app.daily_agent import AgentRunReport
    from app.platform.task_repository import TaskRepository
    from app.platform.task_service import ControlTaskService

    class FakeRunner:
        def run(self, **kwargs):
            return AgentRunReport(
                jobs_found=1,
                new_jobs=1,
                ranked_jobs=[],
                tracked_jobs=1,
                recruiter_targets=[],
                connection_drafts=[],
                hiring_posts=[],
                hiring_post_targets=[],
                diagnostics={"run_id": "run-test"},
            )

    tasks = TaskRepository(tmp_path / "platform.sqlite3")
    service = ControlTaskService(tasks, FakeRunner())
    item = service.submit_agent(locations=["Delhi"], max_posted_hours=6)

    assert item["status"] in {"queued", "running"}
    task_id = item["id"]

    future = service._futures[task_id]
    future.result(timeout=5)

    completed = tasks.get(task_id)
    assert completed["status"] == "completed"
    assert completed["result"]["run_id"] == "run-test"
    service.shutdown()


def test_agent_runner_cannot_bypass_safety_gate(tmp_path, monkeypatch):
    from app.platform.agent_runner import AgentRunError, AgentRunner

    class FakeNotifications:
        def deliver_pending(self, sender, *, limit):
            return 0

        def enqueue(self, **kwargs):
            return None

    from app.config import settings

    monkeypatch.setattr(settings, "agent_enabled", False)
    repo = RunRepository(tmp_path / "platform.sqlite3")
    runner = AgentRunner(repository=repo, notifications=FakeNotifications())

    with pytest.raises(AgentRunError) as error:
        runner.run()

    assert error.value.result.state == RunState.BLOCKED
    assert repo.latest().state == RunState.BLOCKED
