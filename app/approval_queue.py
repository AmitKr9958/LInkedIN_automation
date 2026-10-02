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
                "INSERT INTO approval_queue VALUES(?,?,?,?,?,?,NULL)",
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

    def mark_apply_failed(self, item_id: str, error: str) -> bool:
        message = str(error or "")[:2000]
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE approval_queue SET apply_error=? WHERE id=? AND status='approved'",
                (message, item_id),
            )
            db.commit()
            return cursor.rowcount == 1
