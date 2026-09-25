from __future__ import annotations

from dataclasses import dataclass, asdict
import re


@dataclass(frozen=True)
class MatchReport:
    matched_skills: list[str]
    missing_skills: list[str]
    relevant_terms: list[str]
    keyword_gaps: list[str]
    talking_points: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _tokens(text: str) -> set[str]:
    return {x.lower() for x in re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{1,}", text or "")}


def match_resume_to_job(job_text: str, resume_text: str, skills: list[str] | None = None) -> MatchReport:
    resume = _tokens(resume_text)
    job = _tokens(job_text)
    candidates = [s.strip() for s in (skills or []) if s.strip()]
    matched, missing = [], []
    resume_normalized = " ".join((resume_text or "").lower().split())
    for skill in candidates:
        key = " ".join(skill.lower().split())
        (matched if key in resume_normalized else missing).append(skill)
    terms = sorted(job & resume)
    gaps = sorted((job - resume) & {x.lower() for x in candidates})
    talking = [f"{skill}: present in supplied profile" for skill in matched]
    return MatchReport(matched, missing, terms[:40], gaps, talking)
