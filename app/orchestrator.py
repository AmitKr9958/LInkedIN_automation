from __future__ import annotations

from dataclasses import dataclass
from .approval_queue import ApprovalQueue
from .history import History
from .intelligence import rank_jobs, JobRecord
from .job_preferences import DEFAULT_JOB_PREFERENCES


@dataclass
class DiscoveryReport:
    ranked: list[dict]
    new_count: int


def build_discovery_report(rows: list[dict]) -> DiscoveryReport:
    jobs = [JobRecord(**r) for r in rows]
    ranked = rank_jobs(jobs, DEFAULT_JOB_PREFERENCES)
    history = History()
    new_count = 0
    for item in ranked:
        job = item["job"]
        if history.get_by_url(job.url) is None:
            new_count += 1
        history.upsert_job(job, item["score"], item["reasons"])
    return DiscoveryReport(ranked, new_count)


def queue_message(target: str, message: str) -> str:
    return ApprovalQueue().add("message", target, message)
