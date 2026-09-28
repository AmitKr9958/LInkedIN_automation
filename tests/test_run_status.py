from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.run_status import (
    EXPECTED_CADENCE_SECONDS,
    _health_state,
    read_run_status,
    write_run_status,
)


def test_stale_detection_matches_two_hour_scheduler():
    assert EXPECTED_CADENCE_SECONDS == 2 * 60 * 60
    recent = (datetime.now(timezone.utc) - timedelta(seconds=EXPECTED_CADENCE_SECONDS * 2.9)).isoformat()
    stale = (datetime.now(timezone.utc) - timedelta(seconds=EXPECTED_CADENCE_SECONDS * 3.1)).isoformat()
    assert _health_state(
        last_status="success",
        consecutive_failures=0,
        failure_type=None,
        last_success_at=recent,
    ) == "HEALTHY"
    assert _health_state(
        last_status="success",
        consecutive_failures=0,
        failure_type=None,
        last_success_at=stale,
    ) == "STALE"


def test_write_and_read_success(tmp_path: Path):
    path = tmp_path / "last_run.json"
    write_run_status(
        success=True,
        jobs_found=3,
        hiring_posts=1,
        recruiter_targets=2,
        drafts=1,
        duration_seconds=12.5,
        path=path,
    )
    data = read_run_status(path)
    assert data["last_status"] == "success"
    assert data["last_job_count"] == 3
    assert data["last_hiring_post_count"] == 1
    assert data["last_recruiter_count"] == 2
    assert data["last_draft_count"] == 1
    assert data["last_success_at"] is not None
    assert data["last_error"] is None
    assert data["consecutive_failures"] == 0
    assert data["health_state"] == "HEALTHY"
    assert data["failure_type"] is None


def test_write_failure_preserves_prior_success(tmp_path: Path):
    path = tmp_path / "last_run.json"
    write_run_status(success=True, jobs_found=5, path=path)
    first = read_run_status(path)
    write_run_status(success=False, error="timeout", path=path)
    second = read_run_status(path)
    assert second["last_status"] == "failure"
    assert second["last_error"] == "timeout"
    assert second["last_success_at"] == first["last_success_at"]
    assert second["last_failure_at"] is not None
    assert second["consecutive_failures"] == 1
    assert second["failure_type"] == "timeout"
    assert second["health_state"] in {"DEGRADED", "FAILED"}


def test_consecutive_failures_reset_on_success(tmp_path: Path):
    path = tmp_path / "last_run.json"
    write_run_status(success=False, error="timeout", path=path)
    write_run_status(success=False, error="timeout", path=path)
    mid = read_run_status(path)
    assert mid["consecutive_failures"] == 2
    write_run_status(success=True, jobs_found=1, path=path)
    final = read_run_status(path)
    assert final["consecutive_failures"] == 0
    assert final["health_state"] == "HEALTHY"
    assert final["last_error"] is None


def test_auth_required_classification(tmp_path: Path):
    path = tmp_path / "last_run.json"
    write_run_status(
        success=False,
        error="RuntimeError: session is not verified",
        path=path,
    )
    data = read_run_status(path)
    assert data["failure_type"] == "auth_required"
    assert data["health_state"] == "AUTH_REQUIRED"


def test_profile_locked_classification(tmp_path: Path):
    path = tmp_path / "last_run.json"
    write_run_status(
        success=False,
        error="browser profile is already in use",
        path=path,
    )
    data = read_run_status(path)
    assert data["failure_type"] == "profile_locked"


def test_read_missing(tmp_path: Path):
    data = read_run_status(tmp_path / "missing.json")
    assert data["last_status"] == "never_run"
    assert data["health_state"] == "NEVER_RUN"
    assert data["consecutive_failures"] == 0
