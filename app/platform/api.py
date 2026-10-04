from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .run_repository import RunRepository
from .task_repository import TaskRepository
from .task_service import ControlTaskService


class AgentTaskRequest(BaseModel):
    locations: list[str] = Field(default_factory=list, max_length=20)
    max_posted_hours: float | None = Field(default=None, gt=0, le=720)


def create_control_plane(repository: RunRepository | None = None) -> FastAPI:
    repo = repository or RunRepository()
    tasks = TaskRepository(repo.path)
    task_service = ControlTaskService(tasks)
    app = FastAPI(
        title="LinkedIn Automation Control Plane",
        version="3.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    @app.get("/api/v3/health")
    def health() -> dict:
        return {
            "ok": True,
            "service": "linkedin-automation",
            "version": "3.0",
            "storage": repo.health(),
        }

    @app.get("/api/v3/readiness")
    def readiness() -> dict:
        health = repo.health()
        return {"ready": True, "checks": {"storage": health}}

    @app.post("/api/v3/tasks/agent", status_code=202)
    def submit_agent_task(request: AgentTaskRequest) -> dict:
        try:
            return task_service.submit_agent(
                locations=request.locations or None,
                max_posted_hours=request.max_posted_hours,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v3/tasks/{task_id}")
    def task(task_id: str) -> dict:
        item = tasks.get(task_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return item

    @app.get("/api/v3/tasks")
    def task_list(limit: int = Query(20, ge=1, le=100)) -> dict:
        return {"tasks": tasks.list(limit)}

    @app.get("/api/v3/runs")
    def runs(limit: int = Query(20, ge=1, le=100)) -> dict:
        return {"runs": [item.model_dump(mode="json") for item in repo.list(limit)]}

    @app.get("/api/v3/runs/latest")
    def latest() -> dict:
        item = repo.latest()
        if item is None:
            raise HTTPException(status_code=404, detail="No agent runs recorded")
        return item.model_dump(mode="json")

    return app
