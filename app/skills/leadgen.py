from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass
class Lead:
    name: str
    headline: str = ""
    company: str = ""
    profile_url: str = ""
    reason: str = ""
    def to_dict(self): return asdict(self)

def score_lead(person, keywords: list[str]) -> Lead:
    text = " ".join([person.name, person.headline, getattr(person, "text", "")]).lower()
    hits=[k for k in keywords if k.lower() in text]
    return Lead(person.name, person.headline, "", person.href, f"keyword_matches={','.join(hits)}")
