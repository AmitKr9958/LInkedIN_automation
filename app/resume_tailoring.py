from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TailoredResume:
    summary: str
    relevant_skills: list[str]
    keyword_suggestions: list[str]
    factual_bullets: list[str]

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "relevant_skills": self.relevant_skills,
            "keyword_suggestions": self.keyword_suggestions,
            "factual_bullets": self.factual_bullets,
        }


def tailor_resume(job_text: str, resume_text: str, skills: list[str] | None = None) -> TailoredResume:
    supplied = [s.strip() for s in (skills or []) if s.strip()]
    resume_lower = (resume_text or "").lower()
    relevant = [s for s in supplied if s.lower() in resume_lower]
    missing = [s for s in supplied if s.lower() not in resume_lower]
    summary = "Tailored from supplied facts only; no new employers, projects, dates, metrics, or certifications are invented."
    return TailoredResume(summary, relevant, missing, [])
