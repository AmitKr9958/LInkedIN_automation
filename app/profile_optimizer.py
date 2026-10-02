from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .job_preferences import DEFAULT_JOB_PREFERENCES
from .llm_client import LLMError, chat_json, is_configured


SECTION_LIMITS = {
    "headline": 220,
    "about": 2600,
    "experience": 2000,
}


@dataclass(frozen=True)
class ProfileOptimizationReport:
    profile: dict[str, Any]
    score: int
    section_scores: dict[str, int]
    matched_keywords: list[str]
    missing_keywords: list[str]
    findings: list[dict[str, Any]]
    recommendations: list[str]
    drafts: dict[str, Any]
    llm_used: bool
    llm_error: str | None = None
    ai_insights: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _terms() -> list[str]:
    raw = list(DEFAULT_JOB_PREFERENCES.keywords)
    terms = [
        "Power BI", "SQL", "DAX", "Power Query", "Microsoft Fabric",
        "Data Analytics", "Business Intelligence", "Reporting",
    ]
    for value in raw:
        if value not in terms:
            terms.append(value)
    return terms


def _keyword_hits(text: str, terms: list[str]) -> list[str]:
    normalized = _text(text).lower()
    return [term for term in terms if term.lower() in normalized]


def _has_metric(text: str) -> bool:
    return bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:%|percent|x|years?|months?)", text, re.I))


def _section_score(name: str, value: str, target_keywords: list[str]) -> tuple[int, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    text = _text(value)
    score = 0

    if text:
        score += 35
    else:
        findings.append({"severity": "high", "section": name, "issue": "section is empty"})
        return 0, findings

    if name == "headline":
        if len(text) <= SECTION_LIMITS["headline"]:
            score += 20
        else:
            findings.append({"severity": "high", "section": name, "issue": "exceeds 220 characters"})
        if len(_keyword_hits(text, target_keywords)) >= 2:
            score += 25
        else:
            findings.append({"severity": "medium", "section": name, "issue": "headline lacks target-role keywords"})
        if "|" in text or "•" in text or "·" in text:
            score += 10
        else:
            findings.append({"severity": "low", "section": name, "issue": "headline could state role/value areas more clearly"})
    elif name == "about":
        if len(text) <= SECTION_LIMITS["about"]:
            score += 15
        else:
            findings.append({"severity": "high", "section": name, "issue": "about section exceeds 2,600 characters"})
        hits = _keyword_hits(text, target_keywords)
        if len(hits) >= 3:
            score += 20
        else:
            findings.append({"severity": "medium", "section": name, "issue": "add more target-role keywords naturally"})
        if _has_metric(text):
            score += 20
        else:
            findings.append({"severity": "medium", "section": name, "issue": "add quantified outcomes that are already true"})
        if re.search(r"\b(?:recruit|open to|contact|connect|opportunit)", text, re.I):
            score += 10
        else:
            findings.append({"severity": "low", "section": name, "issue": "consider a concise recruiter-facing closing"})
    else:
        if len(text) <= SECTION_LIMITS["experience"]:
            score += 15
        else:
            findings.append({"severity": "medium", "section": name, "issue": "experience content is unusually long"})
        if len(_keyword_hits(text, target_keywords)) >= 3:
            score += 25
        else:
            findings.append({"severity": "medium", "section": name, "issue": "experience lacks target-role keywords"})
        if _has_metric(text):
            score += 25
        else:
            findings.append({"severity": "high", "section": name, "issue": "experience lacks quantified outcomes"})
        if re.search(r"\b(?:built|developed|automated|optimized|reduced|improved|led|delivered|designed)\b", text, re.I):
            score += 10
        else:
            findings.append({"severity": "low", "section": name, "issue": "use action + result language"})
    return min(score, 100), findings


def profile_fingerprint(profile: dict[str, Any]) -> str:
    """Stable fingerprint used to prevent applying a stale approved proposal."""
    import hashlib
    relevant = {
        key: _text(profile.get(key))
        for key in ("url", "name", "headline", "location", "about", "experience", "skills", "featured")
    }
    raw = json.dumps(relevant, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def audit_profile(profile: dict[str, Any]) -> dict[str, Any]:
    terms = _terms()
    sections = {
        "headline": _text(profile.get("headline")),
        "about": _text(profile.get("about")),
        "experience": _text(profile.get("experience")),
        "skills": _text(profile.get("skills")),
        "featured": _text(profile.get("featured")),
    }

    section_scores: dict[str, int] = {}
    findings: list[dict[str, Any]] = []
    for name in ("headline", "about", "experience"):
        score, section_findings = _section_score(name, sections[name], terms)
        section_scores[name] = score
        findings.extend(section_findings)

    for name in ("skills", "featured"):
        if sections[name]:
            section_scores[name] = 100
        else:
            section_scores[name] = 0
            findings.append({"severity": "medium", "section": name, "issue": "section is empty"})

    all_text = "\\n".join(sections.values())
    matched = _keyword_hits(all_text, terms)
    target_terms = [
        "Power BI", "SQL", "DAX", "Power Query", "Microsoft Fabric",
        "Data Analytics", "Business Intelligence", "Reporting",
    ]
    missing = [term for term in target_terms if term.lower() not in all_text.lower()]

    score = round(
        section_scores["headline"] * 0.25
        + section_scores["about"] * 0.20
        + section_scores["experience"] * 0.30
        + section_scores["skills"] * 0.15
        + section_scores["featured"] * 0.10
    )

    recommendations = []
    if not sections["headline"]:
        recommendations.append("Create a keyword-rich headline centered on the target Power BI/BI role family.")
    if not sections["about"]:
        recommendations.append("Add an About section with scope, measurable outcomes, core stack and a recruiter-facing close.")
    if not sections["experience"]:
        recommendations.append("Rewrite experience around action + technology + measurable business impact.")
    if not sections["skills"]:
        recommendations.append("Populate Skills only with technologies and capabilities supported by real experience.")
    if not sections["featured"]:
        recommendations.append("Use Featured to surface evidence such as dashboards, projects, case studies or certifications.")
    if missing:
        recommendations.append(
            "Where truthful, surface missing target keywords naturally: " + ", ".join(missing) + "."
        )
    if not _has_metric(sections["about"] + " " + sections["experience"]):
        recommendations.append("Add verified metrics from real work; do not invent numbers.")

    return {
        "score": score,
        "section_scores": section_scores,
        "matched_keywords": matched,
        "missing_keywords": missing,
        "findings": findings,
        "recommendations": recommendations,
    }


def _safe_drafts(raw: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    drafts = raw.get("drafts") if isinstance(raw, dict) else {}
    if not isinstance(drafts, dict):
        return {}
    result: dict[str, Any] = {}
    for field, limit in SECTION_LIMITS.items():
        value = drafts.get(field)
        if isinstance(value, str):
            value = value.strip()
            if value and len(value) <= limit:
                result[field] = value

    source_numbers = set(re.findall(r"\d+(?:\.\d+)?", json.dumps(profile, ensure_ascii=False)))
    for field, value in list(result.items()):
        generated_numbers = set(re.findall(r"\d+(?:\.\d+)?", value))
        if not generated_numbers.issubset(source_numbers):
            result.pop(field, None)
    return result


def generate_profile_optimization(
    profile: dict[str, Any], *, use_llm: bool = True
) -> ProfileOptimizationReport:
    audit = audit_profile(profile)
    drafts: dict[str, Any] = {}
    ai_insights: dict[str, Any] = {}
    llm_used = False
    llm_error: str | None = None

    if use_llm and is_configured():
        system = (
            "You are the senior AI strategist for a LinkedIn profile optimization workflow. "
            "Return JSON only. Analyze the profile first, then produce practical improvements "
            "for recruiter search relevance, clarity, credible positioning, achievement evidence, "
            "keyword coverage, and consistency. Use ONLY facts, technologies, employers, "
            "achievements and numbers present in the supplied profile. Never invent metrics, "
            "employers, titles, certifications, dates, years, tools, projects, responsibilities, "
            "or outcomes. If evidence is missing, recommend adding it rather than fabricating it. "
            "Keep keywords natural; do not stuff keywords. Draft only; never perform browser actions."
        )
        user = json.dumps(
            {
                "profile": profile,
                "audit": audit,
                "target_roles": DEFAULT_JOB_PREFERENCES.keywords,
                "target_locations": DEFAULT_JOB_PREFERENCES.locations,
                "required_limits": SECTION_LIMITS,
                "schema": {
                    "positioning": "one concise positioning statement grounded in the profile",
                    "priority_actions": ["3-7 prioritized evidence-based improvements"],
                    "keyword_strategy": ["relevant supported keywords to surface naturally"],
                    "section_notes": {
                        "headline": "string",
                        "about": "string",
                        "experience": "string",
                    },
                    "drafts": {
                        "headline": "string",
                        "about": "string",
                        "experience": "string",
                    },
                },
            },
            ensure_ascii=False,
        )
        try:
            ai_raw = chat_json(system=system, user=user, temperature=0.1, max_tokens=3200)
            drafts = _safe_drafts(ai_raw, profile)
            if isinstance(ai_raw, dict):
                positioning = ai_raw.get("positioning")
                if isinstance(positioning, str) and positioning.strip():
                    ai_insights["positioning"] = positioning.strip()[:600]
                for key in ("priority_actions", "keyword_strategy"):
                    value = ai_raw.get(key)
                    if isinstance(value, list):
                        ai_insights[key] = [
                            str(item).strip() for item in value if str(item).strip()
                        ][:7]
                notes = ai_raw.get("section_notes")
                if isinstance(notes, dict):
                    ai_insights["section_notes"] = {
                        section: str(note).strip()[:600]
                        for section, note in notes.items()
                        if section in SECTION_LIMITS and str(note).strip()
                    }
            llm_used = bool(drafts or ai_insights)
        except LLMError as exc:
            llm_error = str(exc)

    return ProfileOptimizationReport(
        profile=profile,
        score=audit["score"],
        section_scores=audit["section_scores"],
        matched_keywords=audit["matched_keywords"],
        missing_keywords=audit["missing_keywords"],
        findings=audit["findings"],
        recommendations=audit["recommendations"] + list(
            ai_insights.get("priority_actions", [])
        ),
        drafts=drafts,
        llm_used=llm_used,
        llm_error=llm_error,
        ai_insights=ai_insights,
    )
