from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from ..config import settings
from ..daily_agent import AgentRunReport, run_agent_once
from ..job_preferences import DEFAULT_JOB_PREFERENCES
from ..run_lock import AgentAlreadyRunning, agent_lock
from ..run_status import write_run_status
from ..telegram_notify import build_agent_completion_message, send_telegram_message_detailed
from .logging import configure_logging, set_run_id
from .models import AgentRunResult, RunState
from .notification_repository import NotificationRepository
from .run_repository import RunRepository

logger = logging.getLogger(__name__)


class AgentRunError(RuntimeError):
    def __init__(self, message: str, result: AgentRunResult):
        super().__init__(message)
        self.result = result


class AgentRunner:
    """Single execution boundary used by CLI, dashboard and future API workers."""

    def __init__(
        self,
        repository: RunRepository | None = None,
        notifications: NotificationRepository | None = None,
    ) -> None:
        self.repository = repository or RunRepository()
        self.notifications = notifications or NotificationRepository(self.repository.path)

    def run(
        self,
        *,
        locations: list[str] | None = None,
        max_posted_hours: float | None = None,
    ) -> AgentRunReport:
        configure_logging()
        run_id = uuid.uuid4().hex
        set_run_id(run_id)
        started = datetime.now(timezone.utc)
        clock = time.monotonic()
        window = (
            DEFAULT_JOB_PREFERENCES.posted_within_hours
            if max_posted_hours is None
            else max_posted_hours
        )
        metadata = {
            "freshness_hours": window,
            "locations": locations or list(DEFAULT_JOB_PREFERENCES.locations),
        }
        self.repository.start(run_id, started, metadata)
        logger.info("agent run started", extra={"run_id": run_id})
        self._retry_pending_notifications()

        if not settings.agent_enabled:
            exc = PermissionError(
                "agent execution is disabled by the LINKEDIN_AGENT_ENABLED safety gate"
            )
            result = self._failure(run_id, started, clock, exc, RunState.BLOCKED, metadata)
            raise AgentRunError(str(exc), result) from exc

        try:
            with agent_lock():
                report = asyncio.run(
                    run_agent_once(
                        locations=locations,
                        max_posted_hours=max_posted_hours,
                    )
                )
        except AgentAlreadyRunning as exc:
            result = self._failure(run_id, started, clock, exc, RunState.BLOCKED, metadata)
            raise AgentRunError(str(exc), result) from exc
        except Exception as exc:
            result = self._failure(run_id, started, clock, exc, RunState.FAILED, metadata)
            raise AgentRunError(str(exc), result) from exc

        finished = datetime.now(timezone.utc)
        duration = round(time.monotonic() - clock, 2)
        report.diagnostics = {**(report.diagnostics or {}), "run_id": run_id}
        result = AgentRunResult(
            run_id=run_id,
            state=RunState.SUCCEEDED,
            started_at=started,
            finished_at=finished,
            duration_seconds=duration,
            jobs_found=report.jobs_found,
            new_jobs=report.new_jobs,
            tracked_jobs=report.tracked_jobs,
            hiring_posts=len(report.hiring_posts),
            recruiter_targets=len(report.recruiter_targets),
            drafts=len(report.connection_drafts),
            stale_jobs_removed=int(
                (report.diagnostics or {}).get("stale_jobs_removed", 0) or 0
            ),
            metadata={
                "timings_seconds": (report.diagnostics or {}).get("timings_seconds", {}),
                "run_id": run_id,
            },
        )
        self.repository.finish(result)
        write_run_status(
            success=True,
            jobs_found=result.jobs_found,
            new_jobs=result.new_jobs,
            hiring_posts=result.hiring_posts,
            recruiter_targets=result.recruiter_targets,
            drafts=result.drafts,
            duration_seconds=duration,
            started_at=started.isoformat(),
        )
        self._queue_completion(result, freshness_hours=float(window))
        logger.info("agent run completed", extra={"run_id": run_id})
        return report

    def _failure(
        self,
        run_id: str,
        started: datetime,
        clock: float,
        exc: Exception,
        state: RunState,
        metadata: dict[str, Any],
    ) -> AgentRunResult:
        finished = datetime.now(timezone.utc)
        duration = round(time.monotonic() - clock, 2)
        result = AgentRunResult(
            run_id=run_id,
            state=state,
            started_at=started,
            finished_at=finished,
            duration_seconds=duration,
            error_type=type(exc).__name__,
            error_message=str(exc),
            metadata={**metadata, "run_id": run_id},
        )
        self.repository.finish(result)
        write_run_status(
            success=False,
            duration_seconds=duration,
            error=str(exc),
            started_at=started.isoformat(),
        )
        self._queue_completion(result, freshness_hours=float(metadata["freshness_hours"]))
        logger.exception("agent run failed", extra={"run_id": run_id})
        return result

    def _queue_completion(self, result: AgentRunResult, *, freshness_hours: float) -> None:
        message = build_agent_completion_message(
            success=result.state == RunState.SUCCEEDED,
            duration_seconds=result.duration_seconds,
            jobs=result.jobs_found,
            new_jobs=result.new_jobs,
            tracked_jobs=result.tracked_jobs,
            hiring_posts=result.hiring_posts,
            recruiter_targets=result.recruiter_targets,
            connection_drafts=result.drafts,
            stale_jobs_removed=result.stale_jobs_removed,
            freshness_hours=freshness_hours,
            error_message=result.error_message or "",
        )
        self.notifications.enqueue(
            notification_id=f"agent-completion-{result.run_id}",
            event_key=f"agent-run:{result.run_id}:completion",
            channel="telegram",
            message=message,
        )
        self._retry_pending_notifications(limit=5)

    def _retry_pending_notifications(self, *, limit: int = 20) -> None:
        delivered = self.notifications.deliver_pending(
            send_telegram_message_detailed,
            limit=limit,
        )
        if delivered:
            logger.info("delivered pending Telegram notifications: %s", delivered)
