from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from .config import ROOT

DB_PATH = ROOT / "data" / "activity.sqlite3"


def _db_file(path: str | Path | None) -> Path:
    return Path(path) if path is not None else DB_PATH

def init_db(path: str | Path | None = None) -> None:
    db_path = _db_file(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT,
            status TEXT NOT NULL,
            details TEXT
        )""")
        con.commit()

def log_activity(
    action: str,
    target: str = "",
    status: str = "ok",
    details: str = "",
    path: str | Path | None = None,
) -> None:
    db_path = _db_file(path)
    init_db(db_path)
    with sqlite3.connect(db_path) as con:
        con.execute("INSERT INTO activity(created_at, action, target, status, details) VALUES (?, ?, ?, ?, ?)",
                    (datetime.now(timezone.utc).isoformat(), action, target, status, details))
        con.commit()
