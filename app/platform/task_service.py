from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from .agent_runner import AgentRunError, AgentRunner
from .task_repository import TaskRepository

logger = logging.getLogger(__name__)


class ControlTaskService:
    """Own durable task submission and execution for all control-plane callers."""

    AGENT_KIND = "agent"

    def __init__(
        self,
        repository: TaskRepository | None = None,
        runner: AgentRunner | None = None,
    ) -> None:
        self.repository = repository or TaskRepository()
        self.runner = runner or AgentRunner()
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="linkedin-control",
        )
        self._lock = threading.Lock()
        self._futures: dict[str, Future[Any]] = {}

    def submit_agent(
        self,
        *,
        locations: list[str] | None = None,
        max_posted_hours: float | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if self.repository.has_active(self.AGENT_KIND):
                raise RuntimeError("an agent control task is already queued or running")
            task_id = uuid.uuid4().hex
            self.repository.create(task_id, self.AGENT_KIND)
            future = self._executor.submit(
                self._run_agent,
                task_id,
                locations,
                max_posted_hours,
            )
            self._futures[task_id] = future
            return self.repository.get(task_id) or {
                "id": task_id,
                "kind": self.AGENT_KIND,
                "status": "queued",
            }

    def _run_agent(
        self,
        task_id: str,
        locations: list[str] | None,
        max_posted_hours: float | None,
    ) -> None:
        self.repository.mark_running(task_id)
        try:
            report = self.runner.run(
                locations=locations,
                max_posted_hours=max_posted_hours,
            )
            self.repository.mark_completed(
                task_id,
                {
                    "run_id": self._run_id_from_report(report),
                    "report": report.to_dict(),
                },
            )
        except AgentRunError as exc:
            self.repository.mark_failed(task_id, exc)
        except Exception as exc:
            self.repository.mark_failed(task_id, exc)
            logger.exception("control task failed", extra={"task_id": task_id})
        finally:
            with self._lock:
                self._futures.pop(task_id, None)

    @staticmethod
    def _run_id_from_report(report: Any) -> str | None:
        diagnostics = getattr(report, "diagnostics", None) or {}
        return diagnostics.get("run_id")

    def get(self, task_id: str) -> dict[str, Any] | None:
        return self.repository.get(task_id)

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)
