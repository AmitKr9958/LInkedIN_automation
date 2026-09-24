from __future__ import annotations

import re

from .voice import VoiceProfile, DEFAULT_VOICE, audit_voice


def audit_post(text: str, voice: VoiceProfile = DEFAULT_VOICE) -> dict:
    text = text.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first = lines[0] if lines else ""
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    voice_report = audit_voice(text, voice)
    issues: list[dict] = []
    checks: dict[str, bool] = {}

    checks["has_hook"] = bool(first)
    checks["reasonable_length"] = voice.post_min_chars <= len(text) <= voice.post_max_chars
    checks["has_specific_number"] = voice_report["specificity_hint"]
    checks["not_overlong"] = len(text) <= 3000
    checks["paragraph_structure"] = 2 <= len(paragraphs) <= 12
    checks["em_dash_density"] = voice_report["em_dash_ok"]
    checks["avoid_terms"] = not bool(voice_report["avoid_term_hits"])
    checks["has_cta_or_question"] = bool(re.search(r"\?|\b(what do you think|have you|would you)\b", text, re.I))

    if not checks["has_hook"]:
        issues.append({"code": "missing_hook", "message": "Add a clear opening line."})
    if not checks["reasonable_length"]:
        issues.append({"code": "length", "message": f"Target roughly {voice.post_min_chars}-{voice.post_max_chars} characters."})
    if not checks["has_specific_number"]:
        issues.append({"code": "specificity", "message": "Consider adding a concrete number, result, date, or example."})
    if not checks["paragraph_structure"]:
        issues.append({"code": "structure", "message": "Use short, readable paragraphs."})
    if not checks["em_dash_density"]:
        issues.append({"code": "em_dash_density", "message": "Reduce em-dash density."})
    if not checks["avoid_terms"]:
        issues.append({"code": "generic_ai_terms", "message": "Replace generic AI-style vocabulary.", "terms": voice_report["avoid_term_hits"]})
    if not checks["has_cta_or_question"]:
        issues.append({"code": "cta", "message": "Consider ending with a useful question or discussion prompt."})

    return {
        "passed": not issues,
        "checks": checks,
        "issues": issues,
        "voice": voice_report,
        "paragraphs": len(paragraphs),
    }
