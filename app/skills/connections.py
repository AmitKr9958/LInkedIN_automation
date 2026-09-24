from __future__ import annotations
from ..approval import require_approval
from ..drafting import connection_note
from ..store import log_activity

def draft_connection(target: str, note: str = "", role: str = "", skills: list[str] | None = None) -> dict:
    if not note.strip() and role:
        note = connection_note(target, role, skills or []).text
    log_activity("connection_drafted", target, "drafted", f"note_chars={len(note)}")
    return {"action":"connection_request","target":target,"note":note,"status":"drafted"}

def approve_connection(target: str, note: str = "") -> None:
    require_approval("connection_request")
    return None
