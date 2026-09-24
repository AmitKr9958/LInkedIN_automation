from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass
class ContentDraft:
    kind: str
    text: str
    metadata: dict


HOOK_PATTERNS = {
    "contrarian": "Most people think {topic} works one way. My experience suggests the opposite.",
    "story": "I learned something about {topic} the hard way.",
    "number": "{number} things I wish I knew about {topic}.",
    "question": "What would change if you approached {topic} differently?",
}


def content_plan(theme: str, audience: str, days: int = 7) -> list[dict]:
    days = max(1, min(days, 31))
    pillars = ["authority", "experience", "community", "practical", "reflection"]
    formats = ["text", "story", "checklist", "case study", "question"]
    return [
        {
            "day": i + 1,
            "pillar": pillars[i % len(pillars)],
            "format": formats[i % len(formats)],
            "theme": theme,
            "audience": audience,
        }
        for i in range(days)
    ]


def extract_hook(text: str) -> dict:
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    first = lines[0] if lines else ""
    lower = first.lower()
    candidates = []
    if "?" in first:
        candidates.append("question")
    if re.search(r"\b\d+(?:\.\d+)?\b", first):
        candidates.append("number")
    if any(x in lower for x in ("i learned", "i failed", "i was wrong", "i used to")):
        candidates.append("story")
    if any(x in lower for x in ("most people", "unpopular", "contrary", "opposite")):
        candidates.append("contrarian")
    return {"hook": first, "candidates": candidates, "confidence": "high" if candidates else "low"}


def write_post(topic: str, angle: str, hook: str = "") -> ContentDraft:
    opening = hook or HOOK_PATTERNS["story"].format(topic=topic)
    text = f"{opening}\n\n{angle}\n\nWhat has your experience with {topic} been?"
    return ContentDraft("post", text, {"topic": topic, "angle": angle})


def humanize(text: str) -> dict:
    cleaned = re.sub(r"\n{3,}", "\n\n", text.strip())
    cleaned = re.sub(r"\b(very unique|game[- ]changing|revolutionary)\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return {"text": cleaned.strip(), "changes": "mechanical cleanup only; no detector-evasion claim"}


def repurpose(source: str, goal: str = "engagement") -> ContentDraft:
    text = " ".join(source.split())
    hook = text[:180].strip()
    body = text[:1200]
    return ContentDraft("repurposed_post", f"{hook}\n\n{body}\n\nWhat is your view?", {"goal": goal})


def draft_comment(post_text: str, point: str) -> ContentDraft:
    return ContentDraft("comment", f"{point}\n\nThe part I found most useful was the connection to the bigger picture.", {"source": post_text[:120]})


def draft_reply(comment_text: str, response: str) -> ContentDraft:
    return ContentDraft("reply", response, {"in_reply_to": comment_text[:120]})


def profile_audit(profile: dict) -> dict:
    fields = ("headline", "about", "experience", "skills", "featured")
    present = {field: bool(profile.get(field)) for field in fields}
    return {"sections": present, "missing": [k for k, v in present.items() if not v]}


def interviewer_questions(topic: str) -> list[str]:
    return [
        f"What specific result did you achieve with {topic}?",
        "What was the baseline before the change?",
        "What was difficult or unexpected?",
        "What would you do differently now?",
        "What evidence can you share without exposing confidential information?",
    ]


def analyze_engagers(rows: list[dict], target_titles: list[str] | None = None) -> list[dict]:
    target_titles = [x.lower() for x in (target_titles or [])]
    output = []
    for row in rows:
        title = str(row.get("title", ""))
        fit = any(term in title.lower() for term in target_titles) if target_titles else None
        item = dict(row)
        item["target_title_match"] = fit
        output.append(item)
    return output


def thread_followups(rows: list[dict]) -> list[dict]:
    result = []
    for row in rows:
        if row.get("author_replied") and row.get("reply_age_hours", 999) <= 72:
            item = dict(row)
            item["action"] = "draft_reply"
            result.append(item)
    return result


def employee_advocacy_plan(team_size: int, goal: str) -> dict:
    team_size = max(1, min(team_size, 1000))
    return {
        "team_size": team_size,
        "goal": goal,
        "cadence": "1-3 posts/member/week",
        "governance": ["voice ownership", "brand safety review", "consent", "measurement"],
    }
