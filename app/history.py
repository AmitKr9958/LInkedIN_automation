from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

class History:
    def __init__(self,path="data/activity.sqlite3"):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.path=path
        with sqlite3.connect(path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS job_history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT, company TEXT, location TEXT, url TEXT,
                score INTEGER, reasons TEXT, first_seen TEXT,
                status TEXT DEFAULT 'new', notes TEXT DEFAULT ''
            )""")
            db.commit()

    def upsert_job(self, job: dict, score: int, reasons: list[str]) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("""INSERT INTO job_history(title,company,location,url,score,reasons,first_seen)
                         VALUES(?,?,?,?,?,?,?)
                         ON CONFLICT(url) DO UPDATE SET score=excluded.score,reasons=excluded.reasons""",
                       (job.get("title",""),job.get("company",""),job.get("location",""),
                        job.get("url",""),score,", ".join(reasons),
                        datetime.now(timezone.utc).isoformat()))
            db.commit()

    def recent(self, limit=50):
        with sqlite3.connect(self.path) as db:
            return db.execute("SELECT title,company,location,url,score,reasons,status,first_seen FROM job_history ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
