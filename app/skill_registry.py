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
    Skill("notifications", "Read-only LinkedIn notification extraction"),
    Skill("connections", "Connection discovery and controlled requests", True),
    Skill("messaging", "Message drafting and controlled sending", True),
    Skill("engagement", "Comments, replies and likes", True),
    Skill("leadgen", "Prospect discovery and outreach plans"),
    Skill("followups", "Follow-up queue and scheduling", True),
    Skill("outreach", "Job-linked recruiter, HR and hiring-manager outreach planning", True),
    Skill("post_writer", "Draft original LinkedIn posts from a topic and angle"),
    Skill("content_planner", "Build multi-day LinkedIn content plans"),
    Skill("comment_drafter", "Draft comments for LinkedIn posts"),
    Skill("reply_handler", "Draft replies to comments and threads"),
    Skill("post_audit", "Audit post drafts for structure, voice and quality"),
    Skill("humanizer", "Audit and clean AI-like writing without detector-evasion claims"),
    Skill("hook_extractor", "Analyze the structure of a supplied post hook"),
    Skill("repurposer", "Adapt supplied source content into LinkedIn-native copy"),
    Skill("profile_optimizer", "Audit profile sections and identify missing information"),
    Skill("interviewer", "Interview the user to build concrete story material"),
    Skill("story_bank", "Persist and retrieve reusable career stories"),
    Skill("engager_analytics", "Analyze supplied engager records"),
    Skill("thread_monitor", "Identify recent author replies needing follow-up"),
    Skill("employee_advocacy", "Create a governed employee advocacy plan"),
]

def list_skills() -> list[Skill]:
    return SKILLS
