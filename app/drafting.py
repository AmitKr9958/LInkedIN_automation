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

def connection_note(name: str, role: str, skills: list[str]) -> Draft:
    skill_text=", ".join(skills[:3]) or "analytics and reporting"
    text=(f"Hi {name}, I’m exploring {role} roles and came across your profile. "
          f"My background includes {skill_text} — I’d value staying connected.")
    if len(text)>300:
        text=text[:297].rstrip()+"..."
    return Draft("connection_note",name,text,"Short note kept within LinkedIn’s 300-character limit")

def post_draft(topic: str, points: list[str]) -> Draft:
    body="\n\n".join([topic]+[f"• {p}" for p in points])
    return Draft("post","self",body,"Structured draft for manual review")


def hiring_contact_message(
    name: str,
    role: str,
    company: str,
    contact_type: str = "",
    matching_reason: str = "",
    skills: list[str] | None = None,
) -> Draft:
    """Draft a concise job-specific message for human review.

    The text is generated from supplied job/contact evidence only. It does not
    send anything to LinkedIn.
    """
    name_text = " ".join(str(name or "").split())
    first_name = name_text.split()[0] if name_text else "there"
    skill_text = ", ".join((skills or [])[:3])
    role_text = role.strip() or "the role"
    company_text = company.strip() or "your team"
    type_text = contact_type.replace("_", " ").strip()

    if type_text in {"recruiter", "talent acquisition", "hr"}:
        opening = f"I came across the {role_text} opportunity at {company_text}"
    elif type_text:
        opening = f"I noticed the {role_text} opportunity at {company_text} and your work with the team"
    else:
        opening = f"I came across the {role_text} opportunity at {company_text}"

    detail = f" My background includes {skill_text}." if skill_text else ""
    text = (
        f"Hi {first_name}, {opening}."
        f" I’m interested in the role and would value any guidance on the hiring process.{detail}"
        " Thanks for your time."
    )
    if len(text) > 600:
        text = text[:597].rstrip() + "..."
    rationale = "Job-specific draft"
    if matching_reason:
        rationale += f"; grounded in: {matching_reason[:180]}"
    return Draft("hiring_contact_message", name, text, rationale)
