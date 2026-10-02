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
    relevance_score: int = 0
    matching_signals: list[str] | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["matching_signals"] = list(self.matching_signals or [])
        return data


_ROLE_SIGNALS = {
    "recruiter": (
        "recruiter", "technical recruiter", "recruiting", "recruitment",
        "talent acquisition", "talent sourcing", "sourcing",
    ),
    "hr": (
        "hr", "human resources", "people partner", "people operations",
        "talent partner", "people & culture",
    ),
    "hiring_manager": (
        "hiring manager", "department manager", "team manager",
        "manager", "lead", "practice head", "function head", "business head",
    ),
    "business_leader": (
        "head of", "director", "senior director", "vice president", "vp",
        "chief", "general manager",
    ),
}

_DOMAIN_TERMS = (
    "power bi", "business intelligence", "bi developer", "bi analyst",
    "data analyst", "data analytics", "analytics", "reporting", "mis analyst",
    "microsoft fabric", "fabric", "sql", "data",
)


def _person_value(person, key: str, default: str = "") -> str:
    if isinstance(person, dict):
        return str(person.get(key, default) or default)
    return str(getattr(person, key, default) or default)


def _norm(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9+#&/.-]+", " ", str(value or "").lower()).split())


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9+#.-]{3,}", _norm(value))}


def classify_target(title: str, text: str = "") -> str:
    """Classify a contact from evidence, without requiring a recruiter title."""
    evidence = _norm(" ".join((title or "", text or "")))
    for target_type in ("recruiter", "hr", "hiring_manager", "business_leader"):
        if any(signal in evidence for signal in _ROLE_SIGNALS[target_type]):
            return target_type
    if any(term in evidence for term in _DOMAIN_TERMS):
        return "domain_leader"
    return "other"


def _role_overlap(job_title: str, evidence: str) -> tuple[bool, int, list[str]]:
    title_norm = _norm(job_title)
    if not title_norm:
        return False, 0, []
    evidence_norm = _norm(evidence)
    signals: list[str] = []
    if title_norm and title_norm in evidence_norm:
        signals.append(f"exact role phrase: {job_title}")
        return True, 4, signals

    job_tokens = {
        token for token in _tokens(title_norm)
        if token not in {"senior", "junior", "lead", "manager", "developer", "engineer", "analyst"}
    }
    overlap = sorted(token for token in job_tokens if token in _tokens(evidence_norm))
    if overlap:
        points = min(3, len(overlap))
        signals.append("role terms: " + ", ".join(overlap[:4]))
        return True, points, signals
    return False, 0, []


def score_target(person, job_title: str = "", company: str = "", job_location: str = "") -> OutreachTarget:
    title = _person_value(person, "headline")
    person_company = _person_value(person, "company")
    location = _person_value(person, "location")
    text = _norm(" ".join([
        _person_value(person, "name"),
        title,
        person_company,
        location,
        _person_value(person, "text"),
    ]))

    score = 0
    signals: list[str] = []
    target_type = classify_target(title, text)

    role_match, role_points, role_signals = _role_overlap(job_title, text)
    score += role_points
    signals.extend(role_signals)

    company_norm = _norm(company)
    if company_norm and company_norm in text:
        score += 4
        signals.append(f"company evidence: {company}")
    if person_company and company_norm and _norm(person_company) == company_norm:
        score += 2
        signals.append("current-company field matches job company")

    role_signal_hits = [
        label
        for label, values in _ROLE_SIGNALS.items()
        if any(value in text for value in values)
    ]
    if role_signal_hits:
        score += 3
        signals.append("hiring-function evidence: " + ", ".join(role_signal_hits))

    domain_hits = [term for term in _DOMAIN_TERMS if term in text]
    if domain_hits:
        score += 2
        signals.append("domain evidence: " + ", ".join(domain_hits[:4]))

    if job_location and location and any(
        token in _norm(location)
        for token in _tokens(job_location)
        if len(token) >= 4
    ):
        score += 1
        signals.append("location overlap")

    if "hiring" in text or "open role" in text or "job opening" in text:
        score += 2
        signals.append("explicit hiring language")

    if target_type == "other" and not role_match and not domain_hits and not company_norm:
        # Generic HR/recruiting words alone are not enough, but an unclassified
        # profile can still qualify when the job/company evidence is concrete.
        score = max(0, score - 2)

    reason = "; ".join(signals) if signals else "No strong hiring evidence found"
    target = OutreachTarget(
        name=_person_value(person, "name"),
        profile_url=_person_value(person, "href") or _person_value(person, "profile_url"),
        title=title,
        company=person_company or company,
        target_type=target_type,
        job_url="",
        relevance_reason=reason,
        relevance_score=score,
        matching_signals=signals,
    )
    log_activity("outreach_targeted", target.name, "ok", f"score={score}; {reason}")
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


def build_outreach_plan(people: list, job: dict, limit: int = 10) -> list[OutreachTarget]:
    """Rank already-read people against one job using multiple evidence signals.

    This function does not perform LinkedIn navigation, scraping, or outreach.
    It only scores person records that the caller already has.
    """
    job_title = str(job.get("title", ""))
    company = str(job.get("company", ""))
    job_location = str(job.get("location", ""))
    targets = []
    for person in people:
        target = score_target(person, job_title, company, job_location)
        # A contact is eligible when there is concrete role/company/domain/hiring
        # evidence. Do not require a particular job title such as Recruiter.
        if target.relevance_score >= 4:
            target.job_url = str(job.get("url") or job.get("href") or "")
            targets.append(target)

    return sorted(
        targets,
        key=lambda item: (item.relevance_score, bool(item.profile_url), item.name.lower()),
        reverse=True,
    )[: max(1, int(limit))]
