from __future__ import annotations
from ..approval import require_approval
from ..drafting import connection_note

def draft_connection(target: str, note: str = "", role: str = "", skills: list[str] | None = None) -> dict:
    if not note.strip() and role:
        note = connection_note(target, role, skills or []).text
    return {"action":"connection_request","target":target,"note":note,"status":"drafted"}

def approve_connection(target: str, note: str = "") -> None:
    require_approval("connection_request")
    return None
