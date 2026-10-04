from __future__ import annotations

from datetime import datetime, timezone

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


def test_task_repository_detects_active_work(tmp_path):
    from app.platform.task_repository import TaskRepository

    repo = TaskRepository(tmp_path / "platform.sqlite3")
    repo.create("task-2", "agent")
    assert repo.has_active("agent") is True
