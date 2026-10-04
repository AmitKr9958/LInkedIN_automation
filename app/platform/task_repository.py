from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import ROOT


class TaskRepository:
    """Durable control-plane task ledger."""

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
                """CREATE TABLE IF NOT EXISTS control_tasks (
                    task_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    result_json TEXT,
                    error_type TEXT,
                    error_message TEXT
                )"""
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_control_tasks_created "
                "ON control_tasks(created_at DESC)"
            )
            con.commit()

    def create(self, task_id: str, kind: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as con:
            con.execute(
                "INSERT INTO control_tasks(task_id,kind,status,created_at) VALUES(?,?,?,?)",
                (task_id, kind, "queued", now),
            )
            con.commit()
        return self.get(task_id) or {"id": task_id, "kind": kind, "status": "queued"}

    def mark_running(self, task_id: str) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE control_tasks SET status='running',started_at=? WHERE task_id=?",
                (datetime.now(timezone.utc).isoformat(), task_id),
            )
            con.commit()

    def mark_completed(self, task_id: str, result: Any = None) -> None:
        payload = json.dumps(result, default=str, ensure_ascii=False)
        with self._connect() as con:
            con.execute(
                """UPDATE control_tasks SET status='completed',finished_at=?,
                   result_json=?,error_type=NULL,error_message=NULL WHERE task_id=?""",
                (datetime.now(timezone.utc).isoformat(), payload, task_id),
            )
            con.commit()

    def mark_failed(self, task_id: str, exc: Exception) -> None:
        with self._connect() as con:
            con.execute(
                """UPDATE control_tasks SET status='failed',finished_at=?,
                   error_type=?,error_message=? WHERE task_id=?""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    type(exc).__name__,
                    str(exc),
                    task_id,
                ),
            )
            con.commit()

    def recover_interrupted(self) -> int:
        """Fail closed for tasks whose worker process disappeared."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as con:
            cursor = con.execute(
                """UPDATE control_tasks
                   SET status='failed',
                       finished_at=?,
                       error_type='ControlPlaneRestarted',
                       error_message='Task interrupted because the control-plane worker restarted'
                   WHERE status IN ('queued','running')""",
                (now,),
            )
            con.commit()
            return cursor.rowcount

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM control_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
        return self._row_to_dict(row) if row is not None else None

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 1000))
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM control_tasks ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        result = None
        if row["result_json"]:
            try:
                result = json.loads(row["result_json"])
            except json.JSONDecodeError:
                result = row["result_json"]
        return {
            "id": row["task_id"],
            "kind": row["kind"],
            "status": row["status"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "result": result,
            "error": (
                f"{row['error_type']}: {row['error_message']}"
                if row["error_type"] else None
            ),
        }

    def has_active(self, kind: str) -> bool:
        with self._connect() as con:
            row = con.execute(
                "SELECT 1 FROM control_tasks WHERE kind=? "
                "AND status IN ('queued','running') LIMIT 1",
                (kind,),
            ).fetchone()
        return row is not None

    def prune(self, keep: int = 200) -> None:
        keep = max(50, min(keep, 1000))
        with self._connect() as con:
            con.execute(
                """DELETE FROM control_tasks
                   WHERE status NOT IN ('queued','running')
                     AND task_id NOT IN (
                        SELECT task_id FROM control_tasks
                        WHERE status NOT IN ('queued','running')
                        ORDER BY created_at DESC LIMIT ?
                     )""",
                (keep,),
            )
            con.commit()
