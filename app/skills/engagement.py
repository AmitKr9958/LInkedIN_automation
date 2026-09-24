from __future__ import annotations
from ..approval import require_approval

def draft_engagement(action: str, target: str, text: str = "") -> dict:
    return {"action":action,"target":target,"text":text,"status":"drafted"}

def approve_engagement(action: str) -> None:
    require_approval(action)
