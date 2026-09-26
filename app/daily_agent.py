from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable

from .application_tracker import ApplicationTracker
from .job_normalize import dedupe_jobs
from .job_preferences import DEFAULT_JOB_PREFERENCES, DEFAULT_JOB_SEARCH_QUERY
from .orchestrator import build_discovery_report
from .outreach import OutreachTarget, build_outreach_plan, draft_connection
from .skill_runtime import run_read


@dataclass
class AgentRunReport:
    jobs_found: int
    new_jobs: int
    ranked_jobs: list[dict]
    tracked_jobs: int
    recruiter_targets: list[dict]
    connection_drafts: list[dict]
    diagnostics: dict[str, Any]
    mode: str = "read-draft-approval"

    def to_dict(self) -> dict:
        return asdict(self)


def _job_rows(data: Any) -> list[dict]:
    rows = []
    for item in data or []:
        row = item.to_dict() if hasattr(item, "to_dict") else dict(item)
        rows.append(
            {
                "title": row.get("title", ""),
                "company": row.get("company", ""),
                "location": row.get("location", ""),
                "url": row.get("href") or row.get("url", ""),
                "posted_text": row.get("posted", ""),
                "posted_hours": row.get("posted_hours"),
                "description": row.get("text", ""),
                "easy_apply": bool(row.get("easy_apply", False)),
                "source": "linkedin",
            }
        )
    return dedupe_jobs(rows)


def build_agent_report(
    job_batches: list[list[dict]],
    people: list[Any] | None = None,
    *,
    tracker: ApplicationTracker | None = None,
) -> AgentRunReport:
    rows = dedupe_jobs([row for batch in job_batches for row in batch])
    discovery = build_discovery_report(rows)
    ranked = discovery.ranked
    tracker = tracker or ApplicationTracker()
    tracked = 0

    for item in ranked[:5]:
        job = item["job"]
        url = str(job.get("url", "")).strip()
        if not url:
            continue
        tracker.add(url, str(job.get("title", "")), str(job.get("company", "")))
        tracked += 1

    targets: list[OutreachTarget] = []
    drafts: list[dict] = []
    if people and ranked:
        targets = build_outreach_plan(people, ranked[0]["job"])[:5]
        for target in targets:
            drafts.append(draft_connection(target, ranked[0]["job"].get("title", ""), ["Power BI", "SQL", "Data Analytics"]))

    return AgentRunReport(
        jobs_found=len(rows),
        new_jobs=discovery.new_count,
        ranked_jobs=ranked[:10],
        tracked_jobs=tracked,
        recruiter_targets=[target.to_dict() for target in targets],
        connection_drafts=drafts,
        diagnostics={},
    )


async def run_agent_once(
    *,
    locations: list[str] | None = None,
    query: str = DEFAULT_JOB_SEARCH_QUERY,
    max_posted_hours: float | None = None,
    read_fn: Callable[..., Awaitable[Any]] = run_read,
    tracker: ApplicationTracker | None = None,
) -> AgentRunReport:
    locations = locations or list(DEFAULT_JOB_PREFERENCES.locations)
    batches: list[list[dict]] = []
    diagnostics: dict[str, Any] = {}

    for location in locations:
        result = await read_fn(
            "jobs",
            keywords=query,
            location=location,
            max_posted_hours=(
                float(DEFAULT_JOB_PREFERENCES.posted_within_hours)
                if max_posted_hours is None
                else max_posted_hours
            ),
        )
        batches.append(_job_rows(result.data))
        if getattr(result, "diagnostics", None):
            diagnostics[location] = result.diagnostics

    people: list[Any] = []
    # Recruiter discovery is read-only and only runs when there are matching jobs.
    if any(batches):
        result = await read_fn("people", query="Power BI recruiter")
        people = list(result.data or [])

    report = build_agent_report(batches, people, tracker=tracker)
    report.diagnostics = diagnostics
    return report
