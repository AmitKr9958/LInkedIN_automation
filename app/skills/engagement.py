from __future__ import annotations
from ..approval import require_approval
from ..store import log_activity

def draft_engagement(action: str, target: str, text: str = "") -> dict:
    log_activity("engagement_drafted", target, "drafted", f"type={action}")
    return {"action":action,"target":target,"text":text,"status":"drafted"}

def approve_engagement(action: str) -> None:
    require_approval(action)
