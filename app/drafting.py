from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Draft:
    kind: str
    target: str
    text: str
    rationale: str = ""

def recruiter_message(name: str, role: str, skills: list[str]) -> Draft:
    skill_text=", ".join(skills[:4])
    text=(f"Hi {name}, I’m interested in the {role} opportunity. "
          f"My background includes {skill_text}. I’d be glad to connect and "
          f"discuss how my experience could align with the role.")
    return Draft("recruiter_message",name,text,"Concise role + relevant skills")

def followup_message(name: str, role: str) -> Draft:
    text=(f"Hi {name}, following up regarding the {role} opportunity. "
          "I remain interested and would be happy to share any additional details needed.")
    return Draft("followup",name,text,"Polite follow-up without pressure")

def post_draft(topic: str, points: list[str]) -> Draft:
    body="\n\n".join([topic]+[f"• {p}" for p in points])
    return Draft("post","self",body,"Structured draft for manual review")
