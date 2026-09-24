from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT

STATUSES = ("new", "shortlisted", "drafted", "applied", "screening", "interview", "offer", "rejected", "withdrawn", "closed")
TRANSITIONS = {
    "new": {"shortlisted", "drafted", "closed"},
    "shortlisted": {"drafted", "applied", "closed"},
    "drafted": {"applied", "closed"},
    "applied": {"screening", "rejected", "withdrawn", "closed"},
    "screening": {"interview", "rejected", "withdrawn", "closed"},
    "interview": {"offer", "rejected", "withdrawn", "closed"},
    "offer": {"closed", "withdrawn"},
    "rejected": set(), "withdrawn": set(), "closed": set(),
}

class ApplicationTracker:
    def __init__(self, path: str | Path | None = None):
        db_path = Path(path) if path is not None else ROOT / "data" / "activity.sqlite3"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(db_path)
        with sqlite3.connect(self.path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS applications(
              job_url TEXT PRIMARY KEY, title TEXT, company TEXT, status TEXT NOT NULL,
              updated_at TEXT NOT NULL, notes TEXT DEFAULT '')""")
            db.commit()

    def add(self, job_url, title="", company="", status="new"):
        if status not in STATUSES:
            raise ValueError("invalid status")
        with sqlite3.connect(self.path) as db:
            db.execute("""INSERT OR IGNORE INTO applications
              (job_url,title,company,status,updated_at) VALUES(?,?,?,?,?)""",
              (job_url, title, company, status, datetime.now(timezone.utc).isoformat()))
            db.commit()

    def transition(self, job_url, new_status, notes=""):
        if new_status not in STATUSES:
            raise ValueError("invalid status")
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT status FROM applications WHERE job_url=?", (job_url,)).fetchone()
            if not row:
                raise KeyError(job_url)
            if new_status not in TRANSITIONS[row[0]]:
                raise ValueError(f"invalid transition {row[0]} -> {new_status}")
            db.execute("UPDATE applications SET status=?,notes=?,updated_at=? WHERE job_url=?",
                       (new_status, notes, datetime.now(timezone.utc).isoformat(), job_url))
            db.commit()

    def list(self, status=None):
        with sqlite3.connect(self.path) as db:
            if status:
                return db.execute("SELECT * FROM applications WHERE status=? ORDER BY updated_at DESC", (status,)).fetchall()
            return db.execute("SELECT * FROM applications ORDER BY updated_at DESC").fetchall()
