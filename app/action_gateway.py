from __future__ import annotations

import json
from dataclasses import dataclass

from .approval_queue import ApprovalQueue
from .policy import policy_from_settings


@dataclass(frozen=True)
class ActionRequest:
    action: str
    target: str
    payload: dict


class ActionGateway:
    """Single safety boundary for every consequential LinkedIn action."""

    def __init__(self, queue: ApprovalQueue | None = None):
        self.queue = queue or ApprovalQueue()
        self._requested = 0

    def request(self, request: ActionRequest) -> str:
        policy = policy_from_settings()
        if not request.action.strip() or not request.target.strip():
            raise ValueError("action and target are required")
        if self._requested >= policy.max_actions_per_run:
            raise RuntimeError(
                f"Run action limit reached ({policy.max_actions_per_run}). "
                "Further account-changing actions are blocked for this run."
            )
        self._requested += 1

        payload = json.dumps(request.payload, ensure_ascii=False)
        if policy.dry_run:
            return self.queue.add(
                f"dry_run:{request.action}",
                request.target,
                payload,
            )
        if policy.require_human_approval:
            return self.queue.add(request.action, request.target, payload)
        raise RuntimeError(
            "Direct account-changing execution is disabled. "
            "Enable an explicit implementation behind the approval queue before "
            "allowing consequential actions."
        )
