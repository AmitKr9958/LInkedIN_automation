from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from .config import ROOT


@dataclass
class Story:
    title: str
    situation: str = ""
    action: str = ""
    result: str = ""
    metric: str = ""
    lesson: str = ""
    tags: str = ""
    story_id: int | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class StoryBank:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else ROOT / "data" / "story_bank.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _init(self) -> None:
        with sqlite3.connect(self.path) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                situation TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL DEFAULT '',
                result TEXT NOT NULL DEFAULT '',
                metric TEXT NOT NULL DEFAULT '',
                lesson TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")
            con.commit()

    def add(self, story: Story) -> Story:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as con:
            cur = con.execute(
                """INSERT INTO stories
                (title,situation,action,result,metric,lesson,tags,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (story.title, story.situation, story.action, story.result,
                 story.metric, story.lesson, story.tags, now, now),
            )
            story.story_id = cur.lastrowid
        story.created_at = now
        story.updated_at = now
        return story

    def list(self, limit: int = 50) -> list[Story]:
        with sqlite3.connect(self.path) as con:
            rows = con.execute(
                """SELECT id,title,situation,action,result,metric,lesson,tags,created_at,updated_at
                   FROM stories ORDER BY id DESC LIMIT ?""", (limit,)
            ).fetchall()
        return [Story(r[1],r[2],r[3],r[4],r[5],r[6],r[7],r[0],r[8],r[9]) for r in rows]

    def search(self, query: str, limit: int = 10) -> list[Story]:
        term = f"%{query}%"
        with sqlite3.connect(self.path) as con:
            rows = con.execute(
                """SELECT id,title,situation,action,result,metric,lesson,tags,created_at,updated_at
                   FROM stories
                   WHERE title LIKE ? OR situation LIKE ? OR action LIKE ? OR result LIKE ? OR metric LIKE ? OR lesson LIKE ? OR tags LIKE ?
                   ORDER BY id DESC LIMIT ?""",
                (term,term,term,term,term,term,term,limit),
            ).fetchall()
        return [Story(r[1],r[2],r[3],r[4],r[5],r[6],r[7],r[0],r[8],r[9]) for r in rows]
