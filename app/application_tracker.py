from __future__ import annotations

import sqlite3
from contextlib import contextmanager
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
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS applications(
              job_url TEXT PRIMARY KEY, title TEXT, company TEXT, status TEXT NOT NULL,
              updated_at TEXT NOT NULL, notes TEXT DEFAULT '',
              discovered_at TEXT, applied_at TEXT, source TEXT DEFAULT '',
              location TEXT DEFAULT '', recruiter TEXT DEFAULT '',
              resume_version TEXT DEFAULT '', next_follow_up TEXT DEFAULT '',
              interview_date TEXT DEFAULT '', salary_notes TEXT DEFAULT '')""")
            existing = {row[1] for row in db.execute("PRAGMA table_info(applications)").fetchall()}
            migrations = {
                "discovered_at": "TEXT", "applied_at": "TEXT", "source": "TEXT DEFAULT ''",
                "location": "TEXT DEFAULT ''", "recruiter": "TEXT DEFAULT ''",
                "resume_version": "TEXT DEFAULT ''", "next_follow_up": "TEXT DEFAULT ''",
                "interview_date": "TEXT DEFAULT ''", "salary_notes": "TEXT DEFAULT ''",
            }
            for column, definition in migrations.items():
                if column not in existing:
                    db.execute(f"ALTER TABLE applications ADD COLUMN {column} {definition}")
            db.execute(
                "UPDATE applications SET discovered_at=COALESCE(discovered_at,updated_at) "
                "WHERE discovered_at IS NULL OR discovered_at=''"
            )
            db.commit()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path)
        try:
            yield db
        finally:
            db.close()

    def add(
        self, job_url, title="", company="", status="new", *,
        source="", location="", recruiter="", resume_version="",
        next_follow_up="", interview_date="", salary_notes="", notes="",
        applied_at="", discovered_at="",
    ):
        job_url = str(job_url or "").strip()
        if not job_url:
            raise ValueError("job_url is required")
        if status not in STATUSES:
            raise ValueError("invalid status")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            db.execute("""INSERT OR IGNORE INTO applications
              (job_url,title,company,status,updated_at,notes,discovered_at,applied_at,
               source,location,recruiter,resume_version,next_follow_up,interview_date,salary_notes)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (job_url, title, company, status, now, notes, discovered_at or now, applied_at,
               source, location, recruiter, resume_version, next_follow_up, interview_date, salary_notes))
            db.commit()

    def update_details(self, job_url, *, source=None, location=None, recruiter=None,
                       resume_version=None, next_follow_up=None, interview_date=None,
                       salary_notes=None, notes=None, applied_at=None, discovered_at=None):
        job_url = str(job_url or "").strip()
        if not job_url:
            raise ValueError("job_url is required")
        fields = {
            "source": source, "location": location, "recruiter": recruiter,
            "resume_version": resume_version, "next_follow_up": next_follow_up,
            "interview_date": interview_date, "salary_notes": salary_notes,
            "notes": notes, "applied_at": applied_at, "discovered_at": discovered_at,
        }
        fields = {k: v for k, v in fields.items() if v is not None}
        with self._connect() as db:
            row = db.execute("SELECT job_url FROM applications WHERE job_url=?", (job_url,)).fetchone()
            if not row:
                raise KeyError(job_url)
            if fields:
                assignments = ", ".join(f"{k}=?" for k in fields)
                values = list(fields.values()) + [datetime.now(timezone.utc).isoformat(), job_url]
                db.execute(
                    f"UPDATE applications SET {assignments}, updated_at=? WHERE job_url=?",
                    values,
                )
                db.commit()
            return True

    def transition(self, job_url, new_status, notes=""):
        job_url = str(job_url or "").strip()
        if not job_url:
            raise ValueError("job_url is required")
        if new_status not in STATUSES:
            raise ValueError("invalid status")
        with self._connect() as db:
            row = db.execute("SELECT status FROM applications WHERE job_url=?", (job_url,)).fetchone()
            if not row:
                raise KeyError(job_url)
            current_status = row[0]
            # Saving an unchanged status from the dashboard is a no-op. This
            # makes the Save button idempotent and avoids presenting a harmless
            # "new -> new" selection as an invalid workflow transition.
            if new_status == current_status:
                return False
            if new_status not in TRANSITIONS[current_status]:
                raise ValueError(f"invalid transition {current_status} -> {new_status}")
            db.execute("UPDATE applications SET status=?,notes=?,updated_at=? WHERE job_url=?",
                       (new_status, notes, datetime.now(timezone.utc).isoformat(), job_url))
            db.commit()
            return True

    def list(self, status=None):
        with self._connect() as db:
            if status:
                return db.execute("SELECT * FROM applications WHERE status=? ORDER BY updated_at DESC", (status,)).fetchall()
            return db.execute("SELECT * FROM applications ORDER BY updated_at DESC").fetchall()
