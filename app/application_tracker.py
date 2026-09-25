from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT

STATUSES = ("new", "drafted", "discovered", "shortlisted", "application_ready", "applied", "recruiter_contacted", "follow_up_due", "response_received", "screening", "interview", "offer", "rejected", "withdrawn", "closed")
TRANSITIONS = {
    "new": {"shortlisted", "drafted", "discovered", "closed"},
    "drafted": {"applied", "application_ready", "closed"},
    "discovered": {"shortlisted", "application_ready", "closed"},
    "shortlisted": {"application_ready", "applied", "drafted", "closed"},
    "application_ready": {"applied", "closed"},
    "applied": {"recruiter_contacted", "follow_up_due", "response_received", "screening", "rejected", "withdrawn", "closed"},
    "recruiter_contacted": {"follow_up_due", "response_received", "screening", "rejected", "withdrawn", "closed"},
    "follow_up_due": {"response_received", "screening", "rejected", "withdrawn", "closed"},
    "response_received": {"screening", "interview", "rejected", "withdrawn", "closed"},
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
              updated_at TEXT NOT NULL, notes TEXT DEFAULT '', source TEXT DEFAULT '',
              application_url TEXT DEFAULT '', recruiter_contact TEXT DEFAULT '', follow_up_date TEXT DEFAULT '')""")
            columns = {row[1] for row in db.execute("PRAGMA table_info(applications)").fetchall()}
            for name in ("source", "application_url", "recruiter_contact", "follow_up_date"):
                if name not in columns:
                    db.execute(f"ALTER TABLE applications ADD COLUMN {name} TEXT DEFAULT ''")
            db.execute("""CREATE TABLE IF NOT EXISTS application_events(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              job_url TEXT NOT NULL, from_status TEXT, to_status TEXT NOT NULL,
              notes TEXT DEFAULT '', created_at TEXT NOT NULL
            )""")
            db.commit()

    def add(self, job_url, title="", company="", status="discovered", source="", application_url="", recruiter_contact="", follow_up_date=""):
        job_url = str(job_url or "").strip()
        if not job_url:
            raise ValueError("job_url is required")
        if status not in STATUSES:
            raise ValueError("invalid status")
        with sqlite3.connect(self.path) as db:
            db.execute("""INSERT OR IGNORE INTO applications
              (job_url,title,company,status,updated_at,source,application_url,recruiter_contact,follow_up_date) VALUES(?,?,?,?,?,?,?,?,?)""",
              (job_url, title, company, status, datetime.now(timezone.utc).isoformat(), source, application_url, recruiter_contact, follow_up_date))
            db.commit()

    def transition(self, job_url, new_status, notes=""):
        job_url = str(job_url or "").strip()
        if not job_url:
            raise ValueError("job_url is required")
        if new_status not in STATUSES:
            raise ValueError("invalid status")
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT status FROM applications WHERE job_url=?", (job_url,)).fetchone()
            if not row:
                raise KeyError(job_url)
            if new_status not in TRANSITIONS[row[0]]:
                raise ValueError(f"invalid transition {row[0]} -> {new_status}")
            now = datetime.now(timezone.utc).isoformat()
            db.execute("UPDATE applications SET status=?,notes=?,updated_at=? WHERE job_url=?",
                       (new_status, notes, now, job_url))
            db.execute("INSERT INTO application_events(job_url,from_status,to_status,notes,created_at) VALUES(?,?,?,?,?)",
                       (job_url, row[0], new_status, notes, now))
            db.commit()

    def list(self, status=None):
        with sqlite3.connect(self.path) as db:
            if status:
                return db.execute("SELECT * FROM applications WHERE status=? ORDER BY updated_at DESC", (status,)).fetchall()
            return db.execute("SELECT * FROM applications ORDER BY updated_at DESC").fetchall()
