"""Persist last agent-run status for local health monitoring.

Never stores credentials, cookies, session tokens, or OTP.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ROOT

STATUS_PATH = ROOT / "data" / "last_run.json"

# Expected cadence for stale-cycle detection (seconds). Matches the
# production read-only scheduler's 2-hour repetition interval.
EXPECTED_CADENCE_SECONDS = 2 * 60 * 60
# Number of missed intervals before health reports STALE.
STALE_INTERVALS = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_commit() -> str | None:
    """Best-effort short commit hash; never fails the run."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return out.decode("ascii", errors="ignore").strip() or None
    except Exception:
        return None


def _classify_failure(error: str | None) -> str | None:
    if not error:
        return None
    text = error.lower()
    if "session is not verified" in text or "not authenticated" in text:
        return "auth_required"
    if (
        "chromium is not installed" in text
        or "executable doesn't exist" in text
        or "chromium could not be started" in text
    ):
        return "browser_unavailable"
    if (
        "browser profile is already in use" in text
        or "user data directory is already in use" in text
        or "singleton" in text
    ):
        return "profile_locked"
    if "already running" in text:
        return "lock_contention"
    if "infrastructure" in text:
        return "infrastructure"
    if "timeout" in text:
        return "timeout"
    return "error"


def _health_state(
    *,
    last_status: str,
    consecutive_failures: int,
    failure_type: str | None,
    last_success_at: str | None,
) -> str:
    if failure_type == "auth_required":
        return "AUTH_REQUIRED"
    if consecutive_failures >= 3 or last_status == "failure" and consecutive_failures >= 2:
        return "FAILED"
    if consecutive_failures > 0 or last_status == "failure":
        return "DEGRADED"
    if last_status == "success":
        # Stale if no success for too long (even if last was success long ago)
        if last_success_at:
            try:
                ts = datetime.fromisoformat(last_success_at.replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - ts).total_seconds()
                if age > EXPECTED_CADENCE_SECONDS * STALE_INTERVALS:
                    return "STALE"
            except Exception:
                pass
        return "HEALTHY"
    if last_status == "never_run":
        return "NEVER_RUN"
    return "UNKNOWN"


def write_run_status(
    *,
    success: bool,
    jobs_found: int = 0,
    new_jobs: int = 0,
    hiring_posts: int = 0,
    recruiter_targets: int = 0,
    drafts: int = 0,
    duration_seconds: float | None = None,
    error: str | None = None,
    started_at: str | None = None,
    version: str = "0.1.0",
    path: Path | None = None,
) -> Path:
    destination = path or STATUS_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)

    previous: dict[str, Any] = {}
    if destination.exists():
        try:
            previous = json.loads(destination.read_text(encoding="utf-8"))
        except Exception:
            previous = {}

    prev_consecutive = int(previous.get("consecutive_failures") or 0)
    if success:
        consecutive = 0
    else:
        consecutive = prev_consecutive + 1

    failure_type = None if success else _classify_failure(error)
    finished = _now()
    last_success_at = previous.get("last_success_at")
    last_failure_at = previous.get("last_failure_at")
    if success:
        last_success_at = finished
    else:
        last_failure_at = finished

    payload: dict[str, Any] = {
        "version": version,
        "commit": _git_commit(),
        "updated_at": finished,
        "last_started_at": started_at or previous.get("last_started_at"),
        "last_finished_at": finished,
        "last_success_at": last_success_at,
        "last_failure_at": last_failure_at,
        "last_job_count": jobs_found,
        "last_new_jobs": new_jobs,
        "last_hiring_post_count": hiring_posts,
        "last_recruiter_count": recruiter_targets,
        "last_draft_count": drafts,
        "last_duration_seconds": duration_seconds,
        "last_error": error if not success else None,
        "last_status": "success" if success else "failure",
        "failure_type": failure_type,
        "consecutive_failures": consecutive,
        "health_state": _health_state(
            last_status="success" if success else "failure",
            consecutive_failures=consecutive,
            failure_type=failure_type,
            last_success_at=last_success_at,
        ),
    }

    destination.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return destination


def read_run_status(path: Path | None = None) -> dict[str, Any]:
    source = path or STATUS_PATH
    if not source.exists():
        return {
            "version": "0.1.0",
            "updated_at": None,
            "last_started_at": None,
            "last_finished_at": None,
            "last_success_at": None,
            "last_failure_at": None,
            "last_job_count": None,
            "last_hiring_post_count": None,
            "last_recruiter_count": None,
            "last_error": None,
            "last_status": "never_run",
            "failure_type": None,
            "consecutive_failures": 0,
            "health_state": "NEVER_RUN",
            "commit": None,
        }
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
        # Recompute health_state so stale detection stays current on read.
        data["health_state"] = _health_state(
            last_status=str(data.get("last_status") or "never_run"),
            consecutive_failures=int(data.get("consecutive_failures") or 0),
            failure_type=data.get("failure_type"),
            last_success_at=data.get("last_success_at"),
        )
        return data
    except Exception as exc:
        return {
            "version": "0.1.0",
            "last_status": "unreadable",
            "last_error": f"{type(exc).__name__}: {exc}",
            "health_state": "UNKNOWN",
            "consecutive_failures": 0,
        }
