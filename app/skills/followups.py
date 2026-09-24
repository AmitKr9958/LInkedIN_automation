from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

@dataclass
class FollowUp:
    target: str
    message: str
    due_at: str
    status: str = "pending"
    def to_dict(self): return asdict(self)

def make_followup(target: str, message: str, due_at: str | None = None) -> FollowUp:
    due_at = due_at or datetime.now(timezone.utc).isoformat()
    return FollowUp(target, message, due_at)
