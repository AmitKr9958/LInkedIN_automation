from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from .run_repository import RunRepository


def create_control_plane(repository: RunRepository | None = None) -> FastAPI:
    repo = repository or RunRepository()
    app = FastAPI(title="LinkedIn Automation Control Plane", version="3.0", docs_url="/docs", redoc_url="/redoc")

    @app.get("/api/v3/health")
    def health() -> dict:
        return {"ok": True, "service": "linkedin-automation", "version": "3.0", "storage": repo.health()}

    @app.get("/api/v3/readiness")
    def readiness() -> dict:
        health = repo.health()
        return {"ready": True, "checks": {"storage": health}}

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
