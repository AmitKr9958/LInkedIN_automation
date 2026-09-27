from __future__ import annotations

from pathlib import Path

from app.run_status import read_run_status, write_run_status


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


def test_read_missing(tmp_path: Path):
    data = read_run_status(tmp_path / "missing.json")
    assert data["last_status"] == "never_run"
