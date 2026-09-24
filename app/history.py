from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
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
                status TEXT DEFAULT 'new', notes TEXT DEFAULT ''
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_job_history_url ON job_history(url)")
            db.commit()

    def upsert_job(self, job: dict, score: int, reasons: list[str]) -> None:
        url = (job.get("url") or "").strip()
        now = datetime.now(timezone.utc).isoformat()
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
                       SET title=?, company=?, location=?, score=?, reasons=?
                       WHERE id=?""",
                    (
                        job.get("title", ""),
                        job.get("company", ""),
                        job.get("location", ""),
                        score,
                        ", ".join(reasons),
                        row[0],
                    ),
                )
            else:
                db.execute(
                    """INSERT INTO job_history
                       (title,company,location,url,score,reasons,first_seen)
                       VALUES(?,?,?,?,?,?,?)""",
                    (
                        job.get("title", ""),
                        job.get("company", ""),
                        job.get("location", ""),
                        url,
                        score,
                        ", ".join(reasons),
                        now,
                    ),
                )
            db.commit()

    def recent(self, limit=50):
        limit = max(1, min(int(limit), 1000))
        with sqlite3.connect(self.path) as db:
            return db.execute(
                """SELECT title,company,location,url,score,reasons,status,first_seen
                   FROM job_history ORDER BY id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
