from __future__ import annotations

from dataclasses import dataclass
from .approval_queue import ApprovalQueue
from .history import History
from .intelligence import rank_jobs, JobRecord
from .job_preferences import DEFAULT_JOB_PREFERENCES
from .store import log_activity


@dataclass
class DiscoveryReport:
    ranked: list[dict]
    new_count: int
    removed_stale: int = 0


def build_discovery_report(
    rows: list[dict],
    *,
    freshness_hours: float | None = None,
) -> DiscoveryReport:
    jobs = [JobRecord(**r) for r in rows]
    ranked = rank_jobs(jobs, DEFAULT_JOB_PREFERENCES)
    history = History()
    # Keep the Jobs dashboard aligned with the same freshness contract as
    # discovery. This runs on every agent cycle, so stale rows are removed even
    # when the current LinkedIn search returns no jobs.
    if freshness_hours is None:
        freshness_hours = float(DEFAULT_JOB_PREFERENCES.posted_within_hours)
    removed = history.cleanup_older_than_hours(float(freshness_hours))
    new_count = 0
    for item in ranked:
        job = item["job"]
        if history.get_by_url(job.get("url", "")) is None:
            new_count += 1
        history.upsert_job(job, item["score"], item["reasons"])
    log_activity(
        "discovery_run",
        "linkedin_jobs",
        "ok",
        f"ranked={len(ranked)} new={new_count} removed_stale={removed} freshness_hours={freshness_hours:g}",
    )
    return DiscoveryReport(ranked, new_count, removed_stale=removed)


def queue_message(target: str, message: str) -> str:
    return ApprovalQueue().add("message", target, message)
