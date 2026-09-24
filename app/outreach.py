from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import re

from .drafting import connection_note
from .store import log_activity


@dataclass
class OutreachTarget:
    name: str
    profile_url: str = ""
    title: str = ""
    company: str = ""
    target_type: str = ""
    job_url: str = ""
    relevance_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


ROLE_PATTERNS = {
    "recruiter": re.compile(r"\b(recruiter|talent acquisition|technical recruiter|recruiting)\b", re.I),
    "hr": re.compile(r"\b(hr|human resources|people partner|talent partner)\b", re.I),
    "hiring_manager": re.compile(r"\b(hiring manager|head of|director|vp|vice president|manager|lead)\b", re.I),
}


def classify_target(title: str) -> str:
    for target_type in ("recruiter", "hr", "hiring_manager"):
        if ROLE_PATTERNS[target_type].search(title or ""):
            return target_type
    return "other"


def score_target(person, job_title: str = "", company: str = "") -> OutreachTarget:
    title = getattr(person, "headline", "") or ""
    target_type = classify_target(title)
    text = " ".join([getattr(person, "name", ""), title, getattr(person, "text", "")]).lower()
    score = 0
    if target_type != "other":
        score += 3
    if company and company.lower() in text:
        score += 2
    if job_title and any(token.lower() in text for token in job_title.split() if len(token) > 3):
        score += 1
    reason = f"target_type={target_type}; relevance_score={score}"
    target = OutreachTarget(
        name=getattr(person, "name", ""),
        profile_url=getattr(person, "href", ""),
        title=title,
        company=company,
        target_type=target_type,
        job_url="",
        relevance_reason=reason,
    )
    log_activity("outreach_targeted", target.name, "ok", reason)
    return target


def draft_connection(target: OutreachTarget, role: str = "", skills: list[str] | None = None) -> dict:
    note = connection_note(target.name, role or target.title, skills or []).text
    payload = {"target": target.to_dict(), "note": note, "status": "drafted"}
    log_activity("connection_drafted", target.name, "drafted", f"target_type={target.target_type}")
    return payload


def draft_followup(target: OutreachTarget, message: str, due_at: str | None = None) -> dict:
    due_at = due_at or datetime.now(timezone.utc).isoformat()
    payload = {"target": target.to_dict(), "message": message, "due_at": due_at, "status": "drafted"}
    log_activity("outreach_followup_drafted", target.name, "drafted", f"due_at={due_at}")
    return payload
