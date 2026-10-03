from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT
from .store import log_activity


@dataclass
class ApprovalItem:
    id: str
    action: str
    target: str
    payload: str
    status: str
    created_at: str


class ApprovalQueue:
    def __init__(self, path: str | None = None):
        db_path = str(ROOT / "data" / "activity.sqlite3") if path is None else path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.path = db_path
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS approval_queue(
                    id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    target TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    decided_at TEXT,
                    applied_at TEXT,
                    apply_error TEXT
                )"""
            )
            columns = {
                row[1]
                for row in db.execute("PRAGMA table_info(approval_queue)").fetchall()
            }
            if "decided_at" not in columns:
                db.execute("ALTER TABLE approval_queue ADD COLUMN decided_at TEXT")
            if "applied_at" not in columns:
                db.execute("ALTER TABLE approval_queue ADD COLUMN applied_at TEXT")
            if "apply_error" not in columns:
                db.execute("ALTER TABLE approval_queue ADD COLUMN apply_error TEXT")
            db.commit()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path)
        try:
            yield db
        finally:
            db.close()

    def add(self, action: str, target: str, payload: str) -> str:
        if not action.strip() or not target.strip():
            raise ValueError("action and target are required")
        item_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            db.execute(
                "INSERT INTO approval_queue(id,action,target,payload,status,created_at,decided_at,applied_at,apply_error) "
                "VALUES(?,?,?,?,?,?,NULL,NULL,NULL)",
                (item_id, action, target, payload, "pending", now),
            )
            db.commit()
        log_activity(
            "approval_requested",
            target,
            "pending",
            f"{action}: {payload[:100]}",
            path=self.path,
        )
        return item_id

    def list_pending(self) -> list[ApprovalItem]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id,action,target,payload,status,created_at "
                "FROM approval_queue WHERE status='pending' ORDER BY created_at"
            ).fetchall()
        return [ApprovalItem(*row) for row in rows]

    def list_approved_connections(self, limit: int = 30) -> list[ApprovalItem]:
        """Return approved connection requests waiting for the user to send manually."""
        limit = max(1, min(int(limit), 30))
        with self._connect() as db:
            rows = db.execute(
                "SELECT id,action,target,payload,status,created_at "
                "FROM approval_queue "
                "WHERE status='approved' AND action='connection_request' "
                "ORDER BY created_at LIMIT ?",
                (limit,),
            ).fetchall()
        return [ApprovalItem(*row) for row in rows]

    def list_approved_messages(self, limit: int = 30) -> list[ApprovalItem]:
        """Return approved, not-yet-completed message approvals for manual sending."""
        limit = max(1, min(int(limit), 30))
        with self._connect() as db:
            rows = db.execute(
                "SELECT id,action,target,payload,status,created_at "
                "FROM approval_queue "
                "WHERE status='approved' AND action='message' "
                "ORDER BY created_at LIMIT ?",
                (limit,),
            ).fetchall()
        return [ApprovalItem(*row) for row in rows]

    def decide_many(self, item_ids: list[str], approved: bool) -> list[str]:
        """Resolve multiple pending approvals; returns IDs that changed."""
        ids = [str(item_id).strip() for item_id in item_ids if str(item_id).strip()]
        if not ids:
            return []
        status = "approved" if approved else "rejected"
        changed: list[str] = []
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            for item_id in ids:
                cursor = db.execute(
                    "UPDATE approval_queue SET status=?, decided_at=? "
                    "WHERE id=? AND status='pending'",
                    (status, now, item_id),
                )
                if cursor.rowcount == 1:
                    changed.append(item_id)
            db.commit()
        for item_id in changed:
            row = self.get(item_id)
            action, target = (row.action, row.target) if row else ("unknown", item_id)
            log_activity("approval_decided", target, status, f"action={action}; batch=true", path=self.path)
        return changed

    def decide(self, item_id: str, approved: bool) -> bool:
        """Resolve one pending item and report whether a state transition occurred."""
        if not item_id.strip():
            raise ValueError("item_id is required")
        status = "approved" if approved else "rejected"
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE approval_queue SET status=?, decided_at=? "
                "WHERE id=? AND status='pending'",
                (status, datetime.now(timezone.utc).isoformat(), item_id),
            )
            db.commit()
            if cursor.rowcount != 1:
                return False
            row = db.execute(
                "SELECT action, target FROM approval_queue WHERE id=?", (item_id,)
            ).fetchone()
        action, target = row if row else (item_id, item_id)
        log_activity("approval_decided", target, status, f"action={action}", path=self.path)
        return True


    def get(self, item_id: str) -> ApprovalItem | None:
        if not item_id.strip():
            raise ValueError("item_id is required")
        with self._connect() as db:
            row = db.execute(
                "SELECT id,action,target,payload,status,created_at FROM approval_queue WHERE id=?",
                (item_id,),
            ).fetchone()
        return ApprovalItem(*row) if row else None

    def mark_applied(self, item_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE approval_queue SET status='applied', applied_at=?, apply_error=NULL WHERE id=? AND status='approved'",
                (datetime.now(timezone.utc).isoformat(), item_id),
            )
            db.commit()
            return cursor.rowcount == 1

    def mark_manual_connection_sent(self, item_id: str) -> bool:
        """Record that the user manually sent an approved LinkedIn connection request."""
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE approval_queue SET status='manual_sent', applied_at=?, apply_error=NULL "
                "WHERE id=? AND status='approved' AND action='connection_request'",
                (datetime.now(timezone.utc).isoformat(), item_id),
            )
            db.commit()
        if cursor.rowcount == 1:
            row = self.get(item_id)
            target = row.target if row else item_id
            log_activity(
                "connection_request_manual_sent",
                target,
                "manual_sent",
                "User confirmed the approved connection request was sent manually.",
                path=self.path,
            )
            return True
        return False

    def mark_manual_sent(self, item_id: str) -> bool:
        """Record that the user manually sent an approved LinkedIn message."""
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE approval_queue SET status='manual_sent', applied_at=?, apply_error=NULL "
                "WHERE id=? AND status='approved' AND action='message'",
                (datetime.now(timezone.utc).isoformat(), item_id),
            )
            db.commit()
        if cursor.rowcount == 1:
            row = self.get(item_id)
            target = row.target if row else item_id
            log_activity(
                "outreach_manual_sent",
                target,
                "manual_sent",
                "User confirmed the approved message was sent manually.",
                path=self.path,
            )
            return True
        return False

    def mark_apply_failed(self, item_id: str, error: str) -> bool:
        message = str(error or "")[:2000]
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE approval_queue SET apply_error=? WHERE id=? AND status='approved'",
                (message, item_id),
            )
            db.commit()
            return cursor.rowcount == 1
