from __future__ import annotations
from ..approval import require_approval
from ..store import log_activity

def draft_message(target: str, message: str) -> dict:
    log_activity("message_drafted", target, "drafted", f"message_chars={len(message)}")
    return {"action":"message","target":target,"message":message,"status":"drafted"}

def approve_message(target: str, message: str) -> None:
    require_approval("message")
    return None
