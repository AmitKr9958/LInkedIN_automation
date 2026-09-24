from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import re

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

    def to_dict(self): return asdict(self)

def _contains_any(text: str, terms: list[str]) -> bool:
    value=text.lower()
    return any(t.lower() in value for t in terms)

def score_job(job: JobRecord, preferences) -> tuple[int, list[str]]:
    score=0
    reasons=[]
    title=(job.title+" "+job.description).lower()
    if _contains_any(job.title, preferences.keywords):
        score += 35; reasons.append("target role keyword")
    elif _contains_any(title, preferences.keywords):
        score += 20; reasons.append("target skill keyword")
    if any(x.lower() in job.location.lower() for x in preferences.locations):
        score += 25; reasons.append("preferred location")
    if job.easy_apply and preferences.easy_apply_preferred:
        score += 10; reasons.append("Easy Apply")
    if preferences.exclude_internships and re.search(r"\bintern(ship)?\b", title):
        score -= 100; reasons.append("internship excluded")
    if preferences.exclude_fresher_roles and re.search(r"\bfresher|entry[ -]?level\b", title):
        score -= 100; reasons.append("fresher/entry-level excluded")
    return score, reasons

def rank_jobs(jobs: list[JobRecord], preferences) -> list[dict]:
    ranked=[]
    for job in jobs:
        score,reasons=score_job(job,preferences)
        ranked.append({"job":job.to_dict(),"score":score,"reasons":reasons})
    return sorted(ranked,key=lambda x:x["score"],reverse=True)
