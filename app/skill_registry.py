from dataclasses import dataclass

@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    mutating: bool = False

SKILLS = [
    Skill("auth", "Login/session verification"),
    Skill("profile", "Profile, headline, about, experience and skills"),
    Skill("jobs", "Job search and job detail extraction"),
    Skill("people", "People and recruiter research"),
    Skill("companies", "Company page research"),
    Skill("posts", "Post extraction and content workflows"),
    Skill("saved", "Saved-post extraction and organization"),
    Skill("connections", "Connection discovery and controlled requests", True),
    Skill("messaging", "Message drafting and controlled sending", True),
    Skill("engagement", "Comments, replies and likes", True),
    Skill("leadgen", "Prospect discovery and outreach plans"),
    Skill("followups", "Follow-up queue and scheduling", True),
]

def list_skills() -> list[Skill]:
    return SKILLS
