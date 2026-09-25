from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse

APPLICANT_PATTERNS = (
    re.compile(r"(?i)\b(?:over|more than)\s+(\d{1,3}(?:,\d{3})*|\d+)\s+applicants?\b"),
    re.compile(r"(?i)\b(\d{1,3}(?:,\d{3})*|\d+)\+?\s+applicants?\b"),
    re.compile(r"(?i)\bbe among the first\s+(\d{1,3}(?:,\d{3})*|\d+)\s+applicants?\b"),
)
EXPERIENCE_RE = re.compile(
    r"(?i)\b(\d{1,2})\s*(?:\+|plus|or more)?\s*(?:-|–|—|to)\s*(\d{1,2})\s*(?:years?|yrs?)\b"
)
EXPERIENCE_SINGLE_RE = re.compile(
    r"(?i)\b(\d{1,2})\s*(?:\+|plus|or more)?\s*(?:years?|yrs?)\b"
)
EXPERIENCE_MIN_RE = re.compile(
    r"(?i)\b(?:minimum|at least)\s+(\d{1,2})\s*(?:years?|yrs?)\b"
)
ROLE_EXPERIENCE_HINTS = {
    "senior": (5, 12),
    "lead": (6, 15),
    "manager": (7, 15),
}


@dataclass(frozen=True)
class ApplicantInfo:
    count: int | None
    text: str | None


@dataclass(frozen=True)
class ExperienceInfo:
    low: int | None
    high: int | None
    detected: bool
    source: str = ""


def parse_applicant_count(text: str) -> ApplicantInfo:
    value = " ".join((text or "").split())
    for pattern in APPLICANT_PATTERNS:
        match = pattern.search(value)
        if match:
            raw = match.group(1)
            try:
                return ApplicantInfo(int(raw.replace(",", "")), match.group(0))
            except ValueError:
                pass
    return ApplicantInfo(None, None)


def parse_experience(text: str, title: str = "") -> ExperienceInfo:
    value = " ".join((text or "").split())
    match = EXPERIENCE_RE.search(value)
    if match:
        low, high = int(match.group(1)), int(match.group(2))
        return ExperienceInfo(min(low, high), max(low, high), True, "range")
    match = EXPERIENCE_MIN_RE.search(value)
    if match:
        return ExperienceInfo(int(match.group(1)), None, True, "minimum")
    match = EXPERIENCE_SINGLE_RE.search(value)
    if match:
        return ExperienceInfo(int(match.group(1)), None, True, "plus")
    lower_title = (title or "").lower()
    for label, bounds in ROLE_EXPERIENCE_HINTS.items():
        if re.search(rf"\b{re.escape(label)}\b", lower_title):
            return ExperienceInfo(bounds[0], bounds[1], True, f"title:{label}")
    return ExperienceInfo(None, None, False, "")


def experience_matches(info: ExperienceInfo, minimum: int, maximum: int) -> bool | None:
    if not info.detected:
        return None
    low = info.low if info.low is not None else 0
    high = info.high if info.high is not None else maximum
    return low <= maximum and high >= minimum


def extract_application_url(links) -> str | None:
    """Return an explicit external application link, never an arbitrary external URL."""
    for item in links or []:
        if isinstance(item, dict):
            href = str(item.get("href") or "")
            label = " ".join(str(item.get(key) or "") for key in ("text", "aria", "title")).lower()
        else:
            href = str(item or "")
            label = ""
        parsed = urlparse(href)
        host = parsed.netloc.lower()
        if parsed.scheme not in {"http", "https"} or not host:
            continue
        if "linkedin.com" in host:
            continue
        if not re.search(r"\b(apply|application|apply now)\b", label):
            continue
        return href
    return None
