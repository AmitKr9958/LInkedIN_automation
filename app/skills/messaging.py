from __future__ import annotations
from ..approval import require_approval

def draft_message(target: str, message: str) -> dict:
    return {"action":"message","target":target,"message":message,"status":"drafted"}

def approve_message(target: str, message: str) -> None:
    require_approval("message")
    return None
