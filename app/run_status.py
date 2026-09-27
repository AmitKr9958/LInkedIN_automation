"""Persist last agent-run status for local health monitoring.

Never stores credentials, cookies, session tokens, or OTP.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ROOT

STATUS_PATH = ROOT / "data" / "last_run.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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

    payload: dict[str, Any] = {
        "version": version,
        "updated_at": _now(),
        "last_success_at": previous.get("last_success_at"),
        "last_failure_at": previous.get("last_failure_at"),
        "last_job_count": jobs_found,
        "last_new_jobs": new_jobs,
        "last_hiring_post_count": hiring_posts,
        "last_recruiter_count": recruiter_targets,
        "last_draft_count": drafts,
        "last_duration_seconds": duration_seconds,
        "last_error": error,
        "last_status": "success" if success else "failure",
    }
    if success:
        payload["last_success_at"] = payload["updated_at"]
    else:
        payload["last_failure_at"] = payload["updated_at"]

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
            "last_success_at": None,
            "last_failure_at": None,
            "last_job_count": None,
            "last_hiring_post_count": None,
            "last_recruiter_count": None,
            "last_error": None,
            "last_status": "never_run",
        }
    try:
        return json.loads(source.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "version": "0.1.0",
            "last_status": "unreadable",
            "last_error": f"{type(exc).__name__}: {exc}",
        }
