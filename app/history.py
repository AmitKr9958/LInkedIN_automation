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
            # A posting timestamp cannot be later than the first discovery of that URL.
            # Older versions recalculated posted_at on every rediscovery, which could
            # make an old LinkedIn job look newly posted. Invalidate only those
            # demonstrably corrupted timestamps; unknown posting age is kept hidden
            # by the dashboard freshness filter until a reliable age is captured.
            db.execute(
                """UPDATE job_history
                   SET posted_at=NULL
                   WHERE posted_at IS NOT NULL AND first_seen IS NOT NULL
                     AND datetime(posted_at) > datetime(first_seen)"""
            )
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
                    "SELECT id,posted_at FROM job_history WHERE url=? ORDER BY id LIMIT 1",
                    (url,),
                ).fetchone()
            if row:
                # posted_at is immutable once established. A later relative age from
                # LinkedIn describes the observation time, not a new posting event.
                db.execute(
                    """UPDATE job_history
                       SET title=?, company=?, location=?, score=?, reasons=?,
                           posted_hours=?, posted_text=?,
                           posted_at=COALESCE(posted_at, ?)
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
        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff = cutoff_dt.isoformat()
        with sqlite3.connect(self.path) as db:
            rows = db.execute(
                "SELECT id,first_seen,posted_hours,posted_at FROM job_history"
            ).fetchall()
            stale_ids = []
            for row in rows:
                posted_at = None
                if row[3]:
                    try:
                        posted_at = datetime.fromisoformat(str(row[3]).replace("Z", "+00:00"))
                        if posted_at.tzinfo is None:
                            posted_at = posted_at.replace(tzinfo=timezone.utc)
                        posted_at = posted_at.astimezone(timezone.utc)
                    except (TypeError, ValueError):
                        posted_at = None
                if posted_at is None:
                    try:
                        age = float(row[2]) if row[2] is not None else None
                    except (TypeError, ValueError):
                        age = None
                    if age is not None and age >= 0 and row[1]:
                        try:
                            first_seen = datetime.fromisoformat(str(row[1]).replace("Z", "+00:00"))
                            if first_seen.tzinfo is None:
                                first_seen = first_seen.replace(tzinfo=timezone.utc)
                            posted_at = first_seen.astimezone(timezone.utc) - timedelta(hours=age)
                        except (TypeError, ValueError):
                            posted_at = None
                if posted_at is None or posted_at < cutoff_dt:
                    stale_ids.append((row[0],))
            if stale_ids:
                db.executemany("DELETE FROM job_history WHERE id=?", stale_ids)
            db.commit()
            return len(stale_ids)

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
