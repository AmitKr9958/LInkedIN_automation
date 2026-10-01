from __future__ import annotations

import json
import sys
from urllib import error, parse, request

from .config import settings


TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
logger = logging.getLogger(__name__)


def _configuration_reason() -> str | None:
    if not settings.telegram_notifications_enabled:
        return "notifications disabled (TELEGRAM_NOTIFICATIONS_ENABLED is not true)"
    if not settings.telegram_bot_token:
        return "bot token missing (TELEGRAM_BOT_TOKEN)"
    if not settings.telegram_chat_id:
        return "chat ID missing (TELEGRAM_CHAT_ID)"
    return None


def _configured() -> bool:
    return _configuration_reason() is None


def send_telegram_message(message: str) -> bool:
    """Send one Telegram message; return False and log a safe diagnostic on failure."""
    reason = _configuration_reason()
    if reason:
        print(f"[telegram] not sent: {reason}", file=sys.stderr)
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
        ok = bool(body.get("ok"))
        if not ok:
            print(
                f"[telegram] API rejected message: {body.get('description', 'unknown error')}",
                file=sys.stderr,
            )
        else:
            print("[telegram] notification sent", file=sys.stderr)
        return ok
    except error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            detail = body.get("description", str(exc))
        except (OSError, ValueError):
            detail = str(exc)
        print(f"[telegram] HTTP error: {detail}", file=sys.stderr)
        return False
    except (OSError, ValueError, error.URLError) as exc:
        print(f"[telegram] transport/response error: {exc}", file=sys.stderr)
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
    ok, reason = send_telegram_message_detailed("\n".join(lines))
    if ok:
        logger.info("Telegram notification sent successfully")
    else:
        logger.warning("Telegram notification not sent: %s", reason)
    return ok
