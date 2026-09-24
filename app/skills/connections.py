from __future__ import annotations
from ..approval import require_approval

def draft_connection(target: str, note: str = "") -> dict:
    return {"action":"connection_request","target":target,"note":note,"status":"drafted"}

def approve_connection(target: str, note: str = "") -> None:
    require_approval("connection_request")
    return None
