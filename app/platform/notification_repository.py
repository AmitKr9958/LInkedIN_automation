from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..config import ROOT


class NotificationRepository:
    """Durable outbox for operator notifications.

    A notification failure must never turn a successful LinkedIn run into a
    failed run. Pending messages remain durable and can be retried later.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else ROOT / "data" / "platform.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=15000")
        return con

    def _ensure_schema(self) -> None:
        with self._connect() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS notification_outbox (
                    notification_id TEXT PRIMARY KEY,
                    event_key TEXT NOT NULL UNIQUE,
                    channel TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    sent_at TEXT,
                    last_error TEXT
                )"""
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_notification_outbox_pending "
                "ON notification_outbox(status, created_at)"
            )
            con.commit()

    def enqueue(self, notification_id: str, event_key: str, channel: str, message: str) -> None:
        with self._connect() as con:
            con.execute(
                """INSERT OR IGNORE INTO notification_outbox
                   (notification_id,event_key,channel,message,status,created_at)
                   VALUES(?,?,?,?,?,?)""",
                (
                    notification_id,
                    event_key,
                    channel,
                    message,
                    "pending",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            con.commit()

    def pending(self, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        with self._connect() as con:
            rows = con.execute(
                """SELECT * FROM notification_outbox
                   WHERE status='pending'
                   ORDER BY created_at ASC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_sent(self, notification_id: str) -> None:
        with self._connect() as con:
            con.execute(
                """UPDATE notification_outbox
                   SET status='sent',sent_at=?,last_error=NULL
                   WHERE notification_id=?""",
                (datetime.now(timezone.utc).isoformat(), notification_id),
            )
            con.commit()

    def mark_failed(self, notification_id: str, error_message: str) -> None:
        with self._connect() as con:
            con.execute(
                """UPDATE notification_outbox
                   SET status='pending',attempts=attempts+1,last_error=?
                   WHERE notification_id=?""",
                (error_message[:1000], notification_id),
            )
            con.commit()

    def deliver_pending(
        self,
        sender: Callable[[str], tuple[bool, str]],
        *,
        limit: int = 20,
    ) -> int:
        delivered = 0
        for item in self.pending(limit):
            ok, detail = sender(item["message"])
            if ok:
                self.mark_sent(item["notification_id"])
                delivered += 1
            else:
                self.mark_failed(item["notification_id"], detail)
        return delivered

    def get(self, notification_id: str) -> dict[str, Any] | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM notification_outbox WHERE notification_id=?",
                (notification_id,),
            ).fetchone()
        return dict(row) if row else None
