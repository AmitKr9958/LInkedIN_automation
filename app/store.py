from datetime import datetime, timezone
import sqlite3
from .config import ROOT

DB_PATH = ROOT / "data" / "activity.sqlite3"

def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT,
            status TEXT NOT NULL,
            details TEXT
        )""")
        con.commit()

def log_activity(action: str, target: str = "", status: str = "ok", details: str = "") -> None:
    init_db()
    with sqlite3.connect(DB_PATH) as con:
        con.execute("INSERT INTO activity(created_at, action, target, status, details) VALUES (?, ?, ?, ?, ?)",
                    (datetime.now(timezone.utc).isoformat(), action, target, status, details))
        con.commit()
