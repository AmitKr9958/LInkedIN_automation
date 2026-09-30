from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import ROOT


class History:
    def __init__(self, path=None):
        db_path = Path(path) if path is not None else ROOT / "data" / "activity.sqlite3"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(db_path)
        with sqlite3.connect(self.path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS job_history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT, company TEXT, location TEXT, url TEXT,
                score INTEGER, reasons TEXT, first_seen TEXT,
                status TEXT DEFAULT 'new', notes TEXT DEFAULT '',
                posted_hours REAL,
                posted_text TEXT,
                posted_at TEXT
            )""")
            # Backward-compatible schema migration for existing local databases.
            columns = {row[1] for row in db.execute("PRAGMA table_info(job_history)").fetchall()}
            for name, ddl in (
                ("posted_hours", "ALTER TABLE job_history ADD COLUMN posted_hours REAL"),
                ("posted_text", "ALTER TABLE job_history ADD COLUMN posted_text TEXT"),
                ("posted_at", "ALTER TABLE job_history ADD COLUMN posted_at TEXT"),
            ):
                if name not in columns:
                    db.execute(ddl)
            db.execute("CREATE INDEX IF NOT EXISTS idx_job_history_url ON job_history(url)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_job_history_posted_at ON job_history(posted_at)")
            db.commit()

    def upsert_job(self, job: dict, score: int, reasons: list[str]) -> None:
        url = (job.get("url") or "").strip()
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        posted_hours = job.get("posted_hours")
        try:
            posted_hours = float(posted_hours) if posted_hours is not None else None
        except (TypeError, ValueError):
            posted_hours = None
        posted_at = (
            (now_dt - timedelta(hours=posted_hours)).isoformat()
            if posted_hours is not None and posted_hours >= 0
            else None
        )
        posted_text = str(job.get("posted_text") or job.get("posted") or "").strip()
        with sqlite3.connect(self.path) as db:
            row = None
            if url:
                row = db.execute(
                    "SELECT id FROM job_history WHERE url=? ORDER BY id LIMIT 1",
                    (url,),
                ).fetchone()
            if row:
                db.execute(
                    """UPDATE job_history
                       SET title=?, company=?, location=?, score=?, reasons=?,
                           posted_hours=?, posted_text=?, posted_at=?
                       WHERE id=?""",
                    (
                        job.get("title", ""),
                        job.get("company", ""),
                        job.get("location", ""),
                        score,
                        ", ".join(reasons),
                        posted_hours,
                        posted_text,
                        posted_at,
                        row[0],
                    ),
                )
            else:
                db.execute(
                    """INSERT INTO job_history
                       (title,company,location,url,score,reasons,first_seen,
                        posted_hours,posted_text,posted_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (
                        job.get("title", ""),
                        job.get("company", ""),
                        job.get("location", ""),
                        url,
                        score,
                        ", ".join(reasons),
                        now,
                        posted_hours,
                        posted_text,
                        posted_at,
                    ),
                )
            db.commit()

    def cleanup_older_than_hours(self, hours: float) -> int:
        """Delete dashboard job-history rows older than the requested posting window.

        Rows discovered before the posting timestamp was persisted use first_seen
        as a one-time conservative fallback. Application records are intentionally
        untouched; only the Jobs dashboard history is pruned.
        """
        hours = float(hours)
        if hours < 0:
            return 0
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with sqlite3.connect(self.path) as db:
            cur = db.execute(
                """DELETE FROM job_history
                   WHERE (posted_at IS NOT NULL AND posted_at < ?)
                      OR (posted_at IS NULL AND first_seen < ?)""",
                (cutoff, cutoff),
            )
            db.commit()
            return int(cur.rowcount or 0)

    def get_by_url(self, url: str):
        """Return the most recent stored job with this exact URL."""
        url = (url or "").strip()
        if not url:
            return None
        with sqlite3.connect(self.path) as db:
            return db.execute(
                """SELECT title,company,location,url,score,reasons,status,first_seen,
                          posted_hours,posted_text,posted_at
                   FROM job_history WHERE url=? ORDER BY id DESC LIMIT 1""",
                (url,),
            ).fetchone()

    def recent(self, limit=50):
        limit = max(1, min(int(limit), 1000))
        with sqlite3.connect(self.path) as db:
            return db.execute(
                """SELECT title,company,location,url,score,reasons,status,first_seen,
                          posted_hours,posted_text,posted_at
                   FROM job_history ORDER BY id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
