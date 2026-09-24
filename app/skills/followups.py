from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from ..store import list_activity, log_activity

FOLLOWUP_STATUSES = ("pending", "drafted", "sent", "done", "skipped")

@dataclass
class FollowUp:
    target: str
    message: str
    due_at: str
    status: str = "pending"
    def to_dict(self): return asdict(self)

def list_followups(limit: int = 50, path=None) -> list[FollowUp]:
    out = []
    for _created_at, _action, target, status, details in list_activity("followup_created", limit, path):
        details = details or ""
        due_at = details.split("due_at=", 1)[1] if "due_at=" in details else ""
        out.append(FollowUp(target=target or "", message="", due_at=due_at, status=status or "pending"))
    return out

def make_followup(target: str, message: str, due_at: str | None = None, path=None) -> FollowUp:
    due_at = due_at or datetime.now(timezone.utc).isoformat()
    for existing in list_followups(path=path):
        if existing.target == target and existing.due_at == due_at:
            return existing
    log_activity("followup_created", target, "pending", f"due_at={due_at}", path=path)
    return FollowUp(target, message, due_at)

def transition_followup(followup: FollowUp, new_status: str, path=None) -> FollowUp:
    if new_status not in FOLLOWUP_STATUSES:
        raise ValueError(f"unknown follow-up status: {new_status}")
    if followup.status in ("done", "skipped"):
        raise ValueError(f"follow-up is already closed: {followup.status}")
    log_activity("followup_status", followup.target, new_status, f"from={followup.status}", path=path)
    followup.status = new_status
    return followup
