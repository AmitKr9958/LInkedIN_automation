from __future__ import annotations

import json
from urllib import error, parse, request

from .config import settings


TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _configured() -> bool:
    return bool(
        settings.telegram_notifications_enabled
        and settings.telegram_bot_token
        and settings.telegram_chat_id
    )


def send_telegram_message(message: str) -> bool:
    """Send one Telegram message; return False instead of breaking the agent."""
    if not _configured():
        return False

    payload = parse.urlencode(
        {
            "chat_id": settings.telegram_chat_id,
            "text": message,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    url = TELEGRAM_API.format(token=settings.telegram_bot_token)
    req = request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with request.urlopen(req, timeout=15) as response:
            body = json.loads(response.read().decode("utf-8"))
        return bool(body.get("ok"))
    except (OSError, ValueError, error.URLError):
        return False


def notify_agent_completion(
    *,
    success: bool,
    duration_seconds: float,
    jobs: int = 0,
    new_jobs: int = 0,
    tracked_jobs: int = 0,
    hiring_posts: int = 0,
    recruiter_targets: int = 0,
    connection_drafts: int = 0,
    stale_jobs_removed: int = 0,
    freshness_hours: float = 4,
    error_message: str = "",
) -> bool:
    """Send a compact completion/failure summary for one agent cycle."""
    status = "✅ COMPLETED" if success else "❌ FAILED"
    lines = [
        "LinkedIn Automation",
        status,
        f"Duration: {duration_seconds:.1f}s",
    ]
    if success:
        lines.extend(
            [
                f"Jobs found: {jobs}",
                f"New jobs: {new_jobs}",
                f"Tracked: {tracked_jobs}",
                f"Hiring posts: {hiring_posts}",
                f"Recruiter targets: {recruiter_targets}",
                f"Connection drafts: {connection_drafts}",
                f"Stale jobs removed: {stale_jobs_removed}",
                f"Freshness window: {freshness_hours:g} hours",
                "Mode: read/draft/approval-gated",
            ]
        )
    elif error_message:
        lines.append(f"Error: {error_message[:700]}")
    lines.append("No LinkedIn account-changing action was executed.")
    return send_telegram_message("\n".join(lines))
