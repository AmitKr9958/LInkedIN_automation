from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RunState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


class AgentRunResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    run_id: str
    state: RunState
    started_at: datetime
    finished_at: datetime
    duration_seconds: float = Field(ge=0)
    jobs_found: int = Field(default=0, ge=0)
    new_jobs: int = Field(default=0, ge=0)
    tracked_jobs: int = Field(default=0, ge=0)
    hiring_posts: int = Field(default=0, ge=0)
    recruiter_targets: int = Field(default=0, ge=0)
    drafts: int = Field(default=0, ge=0)
    stale_jobs_removed: int = Field(default=0, ge=0)
    error_type: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.state == RunState.SUCCEEDED
