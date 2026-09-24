from __future__ import annotations

import json
from dataclasses import dataclass
from .approval_queue import ApprovalQueue
from .config import settings
from .policy import DEFAULT_POLICY


@dataclass(frozen=True)
class ActionRequest:
    action: str
    target: str
    payload: dict


class ActionGateway:
    """Single safety boundary for every consequential LinkedIn action."""

    def __init__(self, queue: ApprovalQueue | None = None):
        self.queue = queue or ApprovalQueue()

    def request(self, request: ActionRequest) -> str:
        DEFAULT_POLICY.validate()
        if not request.action.strip() or not request.target.strip():
            raise ValueError("action and target are required")
        if settings.dry_run:
            return self.queue.add(
                f"dry_run:{request.action}",
                request.target,
                json.dumps(request.payload, ensure_ascii=False),
            )
        if settings.approval_required:
            return self.queue.add(
                request.action,
                request.target,
                json.dumps(request.payload, ensure_ascii=False),
            )
        raise RuntimeError(
            "Direct account-changing execution is disabled. "
            "Use the approval queue for consequential actions."
        )
