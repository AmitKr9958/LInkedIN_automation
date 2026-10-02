from __future__ import annotations

import json
import logging
import sys
import time
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


def telegram_configuration_status() -> dict[str, object]:
    """Return secret-free Telegram configuration diagnostics."""
    reason = _configuration_reason()
    return {
        "configured": reason is None,
        "enabled": bool(settings.telegram_notifications_enabled),
        "has_bot_token": bool(settings.telegram_bot_token),
        "has_chat_id": bool(settings.telegram_chat_id),
        "reason": reason,
    }


def send_telegram_message_detailed(message: str, *, attempts: int = 3) -> tuple[bool, str]:
    """Send one Telegram message with bounded retry and safe diagnostics."""
    reason = _configuration_reason()
    if reason:
        print(f"[telegram] not sent: {reason}", file=sys.stderr)
        return False, reason

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

    last_detail = "Telegram notification failed"
    for attempt in range(1, max(1, attempts) + 1):
        try:
            with request.urlopen(req, timeout=15) as response:
                body = json.loads(response.read().decode("utf-8"))
            if bool(body.get("ok")):
                print("[telegram] notification sent", file=sys.stderr)
                return True, "sent"
            detail = str(body.get("description", "Telegram API rejected the message"))
            last_detail = detail
            print(f"[telegram] API rejected message (attempt {attempt}): {detail}", file=sys.stderr)
            if attempt < max(1, attempts) and not detail.lower().startswith("bad request"):
                time.sleep(attempt)
                continue
            return False, detail
        except error.HTTPError as exc:
            try:
                body = json.loads(exc.read().decode("utf-8"))
                detail = str(body.get("description", str(exc)))
            except (OSError, ValueError):
                detail = str(exc)
            last_detail = detail
            print(f"[telegram] HTTP error (attempt {attempt}): {detail}", file=sys.stderr)
            if attempt < max(1, attempts) and exc.code >= 500:
                time.sleep(attempt)
                continue
            return False, detail
        except (OSError, ValueError, error.URLError) as exc:
            last_detail = str(exc)
            print(f"[telegram] transport/response error (attempt {attempt}): {last_detail}", file=sys.stderr)
            if attempt < max(1, attempts):
                time.sleep(attempt)
                continue
            return False, last_detail

    return False, last_detail


def notify_profile_optimization(
    *,
    score: int,
    llm_used: bool,
    findings: int,
    drafts: int,
    review_id: str | None = None,
    llm_error: str = "",
) -> bool:
    """Send a compact weekly profile-optimization summary."""
    lines = [
        "LinkedIn Profile Optimizer",
        "Profile audit completed",
        f"Audit score: {score}/100",
        f"Findings: {findings}",
        f"Draft sections: {drafts}",
        f"AI drafting: {'enabled' if llm_used else 'not used'}",
    ]
    if review_id:
        lines.append(f"Review queued: {review_id}")
        lines.append("No LinkedIn profile edit was executed.")
    if llm_error:
        lines.append(f"AI note: {llm_error[:300]}")
    ok, reason = send_telegram_message_detailed("\n".join(lines))
    if not ok:
        logger.warning("Profile optimization Telegram notification not sent: %s", reason)
    return ok


def send_telegram_message(message: str) -> bool:
    """Send one Telegram message; return False and log a safe diagnostic on failure."""
    ok, _ = send_telegram_message_detailed(message)
    return ok


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
    freshness_hours: float = 48,
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
