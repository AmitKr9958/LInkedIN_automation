from __future__ import annotations

import re
from typing import Any


_NUMBER_RE = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?(?:\s*\+)?(?=\s*(?:%|percent|x|years?|yrs?|months?|days?|seconds?|secs?|minutes?|mins?|hours?|dashboards?|analysts?|projects?|clients?|reports?|teams?)\b|\b)")
_CERT_RE = re.compile(r"\b(?:DP|PL|AZ|AI)-\d{3}\b", re.I)

# These are factual anchors commonly introduced by profile-writing models.
# They are checked only when they appear in a draft; ordinary prose is not
# rejected merely because it contains common words.
_TECH_TERMS = (
    "Power BI", "Power Query", "DAX", "SQL", "T-SQL", "MySQL", "Microsoft Fabric",
    "Power Automate", "Alteryx", "Tableau", "Snowflake", "VertiPaq", "RLS",
    "Row-Level Security", "Incremental Refresh", "Star Schema", "Snowflake Schema",
    "ETL", "Data Analytics", "Business Intelligence", "ChatGPT",
)
_ROLE_TERMS = (
    "Power BI Developer", "Senior Power BI Developer", "BI Developer", "BI Lead",
    "BI Consultant", "Data Analyst", "MIS Analyst", "Reporting Analyst",
    "Assistant Manager", "Team Lead", "Architect",
)


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _source_text(profile: dict[str, Any]) -> str:
    return _text(
        " ".join(
            str(profile.get(field, "") or "")
            for field in ("name", "headline", "location", "about", "experience", "skills", "featured")
        )
    )


def _numbers(text: str) -> set[str]:
    return {m.group(0).replace(" ", "").lower() for m in _NUMBER_RE.finditer(text)}


def _canonical_number(value: str) -> str:
    normalized = value.replace(" ", "").lower().rstrip("+")\n    if normalized.endswith(".0"):\n        normalized = normalized[:-2]\n    return normalized


def _unsupported_numbers(source: str, draft: str) -> list[str]:
    source_numbers = {_canonical_number(x) for x in _numbers(source)}
    return sorted(
        {x for x in _numbers(draft) if _canonical_number(x) not in source_numbers},
        key=lambda x: (len(x), x),
    )


def _explicit_certifications(source: str) -> set[str]:
    return {m.group(0).upper() for m in _CERT_RE.finditer(source)}


def _unsupported_certifications(source: str, draft: str) -> list[str]:
    allowed = _explicit_certifications(source)
    return sorted({m.group(0).upper() for m in _CERT_RE.finditer(draft) if m.group(0).upper() not in allowed})


def _unsupported_terms(source: str, draft: str, terms: tuple[str, ...]) -> list[str]:
    source_lower = source.lower()
    draft_lower = draft.lower()
    return sorted({term for term in terms if term.lower() in draft_lower and term.lower() not in source_lower})


def validate_profile_drafts(
    profile: dict[str, Any],
    drafts: dict[str, Any],
) -> dict[str, Any]:
    """Validate AI profile drafts against the supplied source evidence.

    This is deliberately conservative. Unsupported factual anchors block live
    publication; stylistic wording remains a human-review concern rather than
    being falsely labelled as a factual violation.
    """
    source = _source_text(profile)
    fields: dict[str, Any] = {}
    blocking: list[dict[str, Any]] = []

    for field in ("headline", "about", "experience"):
        value = _text(drafts.get(field))
        if not value:
            fields[field] = {"status": "not_provided", "issues": []}
            continue

        issues: list[dict[str, Any]] = []
        numbers = _unsupported_numbers(source, value)
        if numbers:
            issues.append({
                "type": "unsupported_numbers",
                "values": numbers,
                "message": "Numeric claims are not present in the supplied profile evidence.",
            })

        certifications = _unsupported_certifications(source, value)
        if certifications:
            issues.append({
                "type": "unsupported_certifications",
                "values": certifications,
                "message": "Certification codes are not explicitly present in the supplied profile evidence.",
            })

        technologies = _unsupported_terms(source, value, _TECH_TERMS)
        if technologies:
            issues.append({
                "type": "unsupported_technologies",
                "values": technologies,
                "message": "Technology/capability claims are not present in the supplied profile evidence.",
            })

        roles = _unsupported_terms(source, value, _ROLE_TERMS)
        if roles:
            issues.append({
                "type": "unsupported_role_claims",
                "values": roles,
                "message": "Role/title claims are not explicitly present in the supplied profile evidence.",
            })

        status = "blocked" if issues else "safe"
        fields[field] = {"status": status, "issues": issues}
        for issue in issues:
            blocking.append({"field": field, **issue})

    return {
        "publishable": not blocking,
        "fields": fields,
        "blocking_issues": blocking,
        "source_evidence": {
            "numeric_claims": sorted(_numbers(source)),
            "certifications": sorted(_explicit_certifications(source)),
            "technology_terms_present": sorted(
                term for term in _TECH_TERMS if term.lower() in source.lower()
            ),
            "role_terms_present": sorted(
                term for term in _ROLE_TERMS if term.lower() in source.lower()
            ),
        },
    }
