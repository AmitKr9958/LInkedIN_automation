from __future__ import annotations

from .content_skills import (
    analyze_engagers, content_plan, draft_comment, draft_reply,
    employee_advocacy_plan, extract_hook, humanize, interviewer_questions,
    profile_audit, repurpose, thread_followups, write_post,
)

READ_CONTENT = {
    "hook_extractor": extract_hook,
    "humanizer": humanize,
    "profile_optimizer": profile_audit,
    "engager_analytics": analyze_engagers,
    "thread_monitor": thread_followups,
}
DRAFT_CONTENT = {
    "post_writer": write_post,
    "content_planner": content_plan,
    "comment_drafter": draft_comment,
    "reply_handler": draft_reply,
    "repurposer": repurpose,
    "interviewer": interviewer_questions,
    "employee_advocacy": employee_advocacy_plan,
}

def dispatch(skill: str, **kwargs):
    if skill in READ_CONTENT:
        return READ_CONTENT[skill](**kwargs)
    if skill in DRAFT_CONTENT:
        return DRAFT_CONTENT[skill](**kwargs)
    raise ValueError(f"Unknown content skill: {skill}")
