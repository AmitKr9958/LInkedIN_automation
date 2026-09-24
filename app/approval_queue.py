from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT


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
        with sqlite3.connect(db_path) as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS approval_queue(
                    id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    target TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    decided_at TEXT
                )"""
            )
            db.commit()

    def add(self, action: str, target: str, payload: str) -> str:
        if not action.strip() or not target.strip():
            raise ValueError("action and target are required")
        item_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT INTO approval_queue VALUES(?,?,?,?,?,?,NULL)",
                (item_id, action, target, payload, "pending", now),
            )
            db.commit()
        return item_id

    def list_pending(self) -> list[ApprovalItem]:
        with sqlite3.connect(self.path) as db:
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
        with sqlite3.connect(self.path) as db:
            cursor = db.execute(
                "UPDATE approval_queue SET status=?, decided_at=? "
                "WHERE id=? AND status='pending'",
                (status, datetime.now(timezone.utc).isoformat(), item_id),
            )
            db.commit()
        return cursor.rowcount == 1
