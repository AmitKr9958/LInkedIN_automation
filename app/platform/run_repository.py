from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import ROOT
from .models import AgentRunResult, RunState


class RunRepository:
    """Durable SQLite repository for operator-visible agent runs.

    The repository is intentionally independent of the legacy activity/history
    tables so the V3 control plane can evolve without breaking existing data.
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
                """CREATE TABLE IF NOT EXISTS agent_runs (
                    run_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    duration_seconds REAL,
                    jobs_found INTEGER NOT NULL DEFAULT 0,
                    new_jobs INTEGER NOT NULL DEFAULT 0,
                    tracked_jobs INTEGER NOT NULL DEFAULT 0,
                    hiring_posts INTEGER NOT NULL DEFAULT 0,
                    recruiter_targets INTEGER NOT NULL DEFAULT 0,
                    drafts INTEGER NOT NULL DEFAULT 0,
                    stale_jobs_removed INTEGER NOT NULL DEFAULT 0,
                    error_type TEXT,
                    error_message TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )"""
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_started ON agent_runs(started_at DESC)")
            con.commit()

    def start(self, run_id: str, started_at: datetime, metadata: dict[str, Any] | None = None) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT INTO agent_runs(run_id,state,started_at,metadata_json) VALUES(?,?,?,?)",
                (run_id, RunState.RUNNING.value, started_at.isoformat(), json.dumps(metadata or {})),
            )
            con.commit()

    def finish(self, result: AgentRunResult) -> None:
        with self._connect() as con:
            con.execute(
                """UPDATE agent_runs SET state=?, finished_at=?, duration_seconds=?,
                   jobs_found=?, new_jobs=?, tracked_jobs=?, hiring_posts=?,
                   recruiter_targets=?, drafts=?, stale_jobs_removed=?,
                   error_type=?, error_message=?, metadata_json=? WHERE run_id=?""",
                (
                    result.state.value,
                    result.finished_at.isoformat(),
                    result.duration_seconds,
                    result.jobs_found,
                    result.new_jobs,
                    result.tracked_jobs,
                    result.hiring_posts,
                    result.recruiter_targets,
                    result.drafts,
                    result.stale_jobs_removed,
                    result.error_type,
                    result.error_message,
                    json.dumps(result.metadata, ensure_ascii=False),
                    result.run_id,
                ),
            )
            con.commit()

    def latest(self) -> AgentRunResult | None:
        with self._connect() as con:
            row = con.execute("SELECT * FROM agent_runs ORDER BY started_at DESC LIMIT 1").fetchone()
        return self._row(row) if row else None

    def list(self, limit: int = 20) -> list[AgentRunResult]:
        limit = max(1, min(limit, 100))
        with self._connect() as con:
            rows = con.execute("SELECT * FROM agent_runs ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._row(row) for row in rows]

    @staticmethod
    def _row(row: sqlite3.Row) -> AgentRunResult:
        finished = row["finished_at"] or row["started_at"]
        return AgentRunResult(
            run_id=row["run_id"], state=row["state"], started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=datetime.fromisoformat(finished), duration_seconds=float(row["duration_seconds"] or 0),
            jobs_found=row["jobs_found"], new_jobs=row["new_jobs"], tracked_jobs=row["tracked_jobs"],
            hiring_posts=row["hiring_posts"], recruiter_targets=row["recruiter_targets"], drafts=row["drafts"],
            stale_jobs_removed=row["stale_jobs_removed"], error_type=row["error_type"],
            error_message=row["error_message"], metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def health(self) -> dict[str, Any]:
        latest = self.latest()
        now = datetime.now(timezone.utc)
        return {
            "ok": True,
            "latest_run_id": latest.run_id if latest else None,
            "latest_state": latest.state.value if latest else RunState.BLOCKED.value,
            "latest_finished_at": latest.finished_at.isoformat() if latest else None,
            "age_seconds": round((now - latest.finished_at.astimezone(timezone.utc)).total_seconds(), 2) if latest else None,
        }
