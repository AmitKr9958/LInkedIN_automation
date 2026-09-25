from __future__ import annotations

from dataclasses import dataclass, asdict
import re

from .job_metadata import ExperienceInfo, experience_matches, parse_experience


@dataclass
class JobRecord:
    title: str
    company: str = ""
    location: str = ""
    url: str = ""
    posted_text: str = ""
    description: str = ""
    easy_apply: bool = False
    source: str = "manual"
    posted_hours: float | None = None
    applicant_count: int | None = None
    applicant_count_text: str | None = None
    experience_low: int | None = None
    experience_high: int | None = None
    experience_detected: bool = False
    application_url: str | None = None

    def to_dict(self):
        return asdict(self)


def _contains_any(text: str, terms: list[str]) -> bool:
    value = text.lower()
    return any(t.lower() in value for t in terms)


def _posted_hours(posted_text: str) -> float | None:
    value = posted_text.strip().lower()
    if not value:
        return None
    if "just now" in value or "minute" in value:
        return 0.0
    if "today" in value:
        return 12.0
    if "yesterday" in value:
        return 36.0

    match = re.search(r"(\d+(?:\.\d+)?)\s*(hour|day|week|month)", value)
    if not match:
        return None

    amount = float(match.group(1))
    unit = match.group(2)
    return {
        "hour": amount,
        "day": amount * 24,
        "week": amount * 24 * 7,
        "month": amount * 24 * 30,
    }[unit]


def _is_remote(location: str, title: str, description: str) -> bool:
    text = f"{location} {title} {description}".lower()
    return "remote" in text


_EXPERIENCE_RE = re.compile(
    r"(\d{1,2})\s*(?:\+|plus\b|or more)?\s*(?:(?:-|–|—|to)\s*(\d{1,2})\s*\+?)?\s*(?:years?|yrs?)\b",
    re.IGNORECASE,
)


def _experience_years(text: str) -> tuple[int, int | None] | None:
    """Parse an experience expectation such as "3-5 years" or "6+ years"."""
    match = _EXPERIENCE_RE.search(text)
    if not match:
        return None
    low = int(match.group(1))
    high = int(match.group(2)) if match.group(2) else None
    if high is None:
        opened = any(
            token in match.group(0).lower() for token in ("+", "plus", "or more")
        )
        if not opened:
            high = low  # a bare "5 years" reads as an exact expectation
    if high is not None and high < low:
        low, high = high, low
    return low, high


def score_job(job: JobRecord, preferences) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    searchable = f"{job.title} {job.description}"

    if _contains_any(job.title, preferences.keywords):
        score += 35
        reasons.append("target role keyword")
    elif _contains_any(searchable, preferences.keywords):
        score += 20
        reasons.append("target skill keyword")

    if any(x.lower() in job.location.lower() for x in preferences.locations):
        score += 25
        reasons.append("preferred location")

    if job.easy_apply and preferences.easy_apply_preferred:
        score += 10
        reasons.append("Easy Apply")

    if job.applicant_count is not None:
        if job.applicant_count < getattr(preferences, "preferred_applicant_count", 25):
            score += 12
            reasons.append("under preferred applicant threshold")
        elif job.applicant_count < getattr(preferences, "acceptable_applicant_count", 50):
            score += 6
            reasons.append("under acceptable applicant threshold")
        else:
            score -= 4
            reasons.append("high applicant count")

    posted_hours = job.posted_hours
    if posted_hours is None:
        posted_hours = _posted_hours(job.posted_text)
    if posted_hours is not None:
        if posted_hours <= preferences.posted_within_hours:
            score += 15
            reasons.append("recent posting")
        else:
            score -= 15
            reasons.append("outside posting window")

    if preferences.remote_only_if_explicit and _is_remote(
        job.location, job.title, job.description
    ):
        explicit_remote = "remote" in job.location.lower() or re.search(
            r"(?i)\b(remote|work from home|wfh)\b", searchable
        )
        if explicit_remote:
            reasons.append("explicit remote")
        else:
            score -= 25
            reasons.append("remote not explicit")

    if job.experience_detected:
        experience = ExperienceInfo(job.experience_low, job.experience_high, True, "job")
    else:
        experience = parse_experience(searchable, job.title)
    experience_match = experience_matches(
        experience,
        preferences.min_experience_years,
        preferences.max_experience_years,
    )
    if experience_match is True:
        score += 10
        reasons.append("experience range matches")
    elif experience_match is False:
        score -= 15
        reasons.append("experience range outside preference")
    else:
        reasons.append("experience requirement unknown")

    if preferences.exclude_internships and re.search(
        r"\bintern(ship)?\b", searchable, re.IGNORECASE
    ):
        score -= 100
        reasons.append("internship excluded")

    if preferences.exclude_fresher_roles and re.search(
        r"\b(fresher|entry[ -]?level|graduate trainee)\b",
        searchable,
        re.IGNORECASE,
    ):
        score -= 100
        reasons.append("fresher/entry-level excluded")

    return score, reasons


def rank_jobs(jobs: list[JobRecord], preferences) -> list[dict]:
    ranked = []
    for job in jobs:
        score, reasons = score_job(job, preferences)
        ranked.append({"job": job.to_dict(), "score": score, "reasons": reasons})
    return sorted(ranked, key=lambda x: x["score"], reverse=True)
