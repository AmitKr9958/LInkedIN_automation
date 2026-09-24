from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from ..store import list_activity, log_activity

FOLLOWUP_STATUSES = ("pending", "drafted", "sent", "responded", "done", "skipped", "declined", "closed")

@dataclass
class FollowUp:
    target: str
    message: str
    due_at: str
    status: str = "pending"
    def to_dict(self): return asdict(self)

def _parse_created(details: str) -> tuple[str, str]:
    details = details or ""
    due_at = ""
    message = ""
    if "due_at=" in details:
        due_at = details.split("due_at=", 1)[1].split(";message=", 1)[0]
    if ";message=" in details:
        message = details.split(";message=", 1)[1]
    return due_at, message

def list_followups(limit: int = 50, path=None) -> list[FollowUp]:
    """Reconstruct current follow-up state from creation and status events."""
    events = list_activity(None, max(limit * 4, 100), path)
    records: dict[tuple[str, str], FollowUp] = {}
    order: list[tuple[str, str]] = []

    for _created_at, action, target, status, details in reversed(events):
        if action == "followup_created":
            due_at, message = _parse_created(details)
            key = (target or "", due_at)
            if key not in records:
                records[key] = FollowUp(target or "", message, due_at, status or "pending")
                order.append(key)
        elif action == "followup_status":
            from_status = ""
            if "from=" in (details or ""):
                from_status = details.split("from=", 1)[1]
            candidates = [key for key, item in records.items() if item.target == (target or "")]
            if candidates:
                key = candidates[-1]
                if not from_status or records[key].status == from_status:
                    records[key].status = status or records[key].status

    return [records[key] for key in order[-limit:]]

def make_followup(target: str, message: str, due_at: str | None = None, path=None) -> FollowUp:
    due_at = due_at or datetime.now(timezone.utc).isoformat()
    for existing in list_followups(path=path):
        if existing.target == target and existing.due_at == due_at:
            return existing
    log_activity("followup_created", target, "pending", f"due_at={due_at};message={message}", path=path)
    return FollowUp(target, message, due_at)

def transition_followup(followup: FollowUp, new_status: str, path=None) -> FollowUp:
    if new_status not in FOLLOWUP_STATUSES:
        raise ValueError(f"unknown follow-up status: {new_status}")
    if followup.status in ("done", "skipped", "declined", "closed"):
        raise ValueError(f"follow-up is already closed: {followup.status}")
    log_activity("followup_status", followup.target, new_status, f"from={followup.status};due_at={followup.due_at}", path=path)
    followup.status = new_status
    return followup

STOP_STATUSES = {"done", "skipped", "responded", "declined", "closed"}

def can_schedule_followup(followup: FollowUp, response_received: bool = False,
                          application_closed: bool = False) -> bool:
    """Return whether a follow-up may still be scheduled."""
    if response_received or application_closed:
        return False
    return followup.status not in STOP_STATUSES

def mark_response(followup: FollowUp, path=None) -> FollowUp:
    if followup.status in STOP_STATUSES:
        return followup
    log_activity("followup_response", followup.target, "responded", f"due_at={followup.due_at}", path=path)
    followup.status = "responded"
    return followup
