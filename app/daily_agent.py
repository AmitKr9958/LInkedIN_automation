from __future__ import annotations

import asyncio

from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable

from .application_tracker import ApplicationTracker
from .job_normalize import dedupe_jobs
from .job_preferences import DEFAULT_JOB_PREFERENCES, DEFAULT_JOB_SEARCH_QUERY
from .orchestrator import build_discovery_report
from .outreach import OutreachTarget, build_outreach_plan, draft_connection
from .skill_runtime import run_read


HIRING_INTENT_PHRASES = (
    "we are hiring", "we're hiring", "hiring for", "hiring:",
    "now hiring", "looking for", "looking to hire", "open position",
    "open role", "job opening", "job openings", "vacancy", "vacancies",
    "join our team", "apply now", "applications open", "immediate joiner",
)


@dataclass
class AgentRunReport:
    jobs_found: int
    new_jobs: int
    ranked_jobs: list[dict]
    tracked_jobs: int
    recruiter_targets: list[dict]
    connection_drafts: list[dict]
    hiring_posts: list[dict]
    hiring_post_targets: list[dict]
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


def _post_rows(data: Any) -> list[dict]:
    rows = []
    for item in data or []:
        row = item.to_dict() if hasattr(item, "to_dict") else dict(item)
        rows.append({
            "author": row.get("author", ""),
            "text": row.get("text", ""),
            "profile_url": row.get("href") or row.get("profile_url", ""),
            "source": "linkedin_post",
        })
    return rows


def _rank_hiring_posts(
    posts: list[dict],
    *,
    locations: list[str],
    keywords: list[str],
    limit: int = 10,
) -> list[dict]:
    ranked = []
    seen: set[str] = set()
    for post in posts:
        text = str(post.get("text", "") or "")
        normalized = " ".join(text.lower().replace("–", " ").replace("—", " ").split())
        if not any(phrase in normalized for phrase in HIRING_INTENT_PHRASES):
            continue
        matched_keywords = [k for k in keywords if k.lower() in normalized]
        if not matched_keywords:
            continue
        matched_locations = [loc for loc in locations if loc.lower() in normalized]
        score = 40 + min(35, 15 * len(matched_keywords))
        reasons = ["hiring intent", "target role: " + ", ".join(matched_keywords[:3])]
        if matched_locations:
            score += 20
            reasons.append("target location: " + ", ".join(matched_locations[:3]))
        elif "remote" in normalized:
            score += 5
            reasons.append("remote mentioned")
        else:
            reasons.append("location not stated")
        key = f"{post.get('author','')}|{text[:240]}"
        if key in seen:
            continue
        seen.add(key)
        ranked.append({"post": post, "score": score, "reasons": reasons})
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:limit]


def build_agent_report(
    job_batches: list[list[dict]],
    people: list[Any] | None = None,
    *,
    tracker: ApplicationTracker | None = None,
    post_batches: list[list[dict]] | None = None,
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
    hiring_posts = _rank_hiring_posts(
        [post for batch in (post_batches or []) for post in batch],
        locations=DEFAULT_JOB_PREFERENCES.locations,
        keywords=DEFAULT_JOB_PREFERENCES.keywords,
    )
    post_targets: list[dict] = []
    for item in hiring_posts[:5]:
        post = item["post"]
        author = str(post.get("author", "")).strip()
        profile_url = str(post.get("profile_url", "")).strip()
        if author and profile_url:
            target = OutreachTarget(
                name=author,
                profile_url=profile_url,
                target_type="hiring-post-author",
            )
            post_targets.append({
                "target": target.to_dict(),
                "score": item["score"],
                "reasons": item["reasons"],
                "post_text": str(post.get("text", ""))[:1000],
            })
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
        hiring_posts=hiring_posts,
        hiring_post_targets=post_targets,
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
    post_batches: list[list[dict]] = []
    diagnostics: dict[str, Any] = {}

    for location in locations:
        last_error = None
        for attempt in range(1, 3):
            try:
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
                break
            except Exception as exc:
                last_error = exc
                if "session is not verified" in str(exc).lower():
                    raise
                if attempt < 2:
                    await asyncio.sleep(1)
        else:
            diagnostics[location] = {
                "skill": "jobs",
                "error": f"{type(last_error).__name__}: {last_error}",
                "retries": 1,
                "final_returned": 0,
            }

    # Scan LinkedIn content-search results and the authenticated personalized
    # home feed for people publicly advertising target roles.
    # This is read-only; it never contacts the author or interacts with the post.
    post_queries = [
        f"hiring {keyword} {location}"
        for keyword in DEFAULT_JOB_PREFERENCES.keywords[:3]
        for location in locations
    ]
    post_queries.extend(
        f"hiring {keyword}" for keyword in DEFAULT_JOB_PREFERENCES.keywords[:3]
    )
    post_window = (
        float(DEFAULT_JOB_PREFERENCES.posted_within_hours)
        if max_posted_hours is None
        else max_posted_hours
    )
    unique_post_queries = list(dict.fromkeys(post_queries))
    for post_query in unique_post_queries:
        try:
            result = await read_fn(
                "posts",
                query=post_query,
                max_posted_hours=post_window,
            )
            post_batches.append(_post_rows(result.data))
        except Exception as exc:
            diagnostics.setdefault("posts", []).append({
                "source": "content-search",
                "query": post_query,
                "error": f"{type(exc).__name__}: {exc}",
            })

    try:
        feed_result = await read_fn(
            "posts",
            feed=True,
            max_posted_hours=post_window,
            max_scrolls=8,
        )
        post_batches.append(_post_rows(feed_result.data))
        diagnostics["feed_scan_candidates"] = len(feed_result.data or [])
        if getattr(feed_result, "diagnostics", None):
            diagnostics["feed_scan"] = feed_result.diagnostics
    except Exception as exc:
        diagnostics.setdefault("posts", []).append({
            "source": "personalized-feed",
            "error": f"{type(exc).__name__}: {exc}",
        })

    people: list[Any] = []
    # Recruiter discovery is read-only and only runs when there are matching jobs.
    # Keep the query broad across the configured BI/data role families; scoring
    # below performs job-specific relevance filtering.
    if any(batches):
        result = await read_fn("people", query="recruiter Power BI Data Analyst")
        people = list(result.data or [])

    report = build_agent_report(
        batches,
        people,
        tracker=tracker,
        post_batches=post_batches,
    )
    diagnostics["post_scan_queries"] = len(unique_post_queries)
    diagnostics["post_scan_candidates"] = sum(len(batch) for batch in post_batches)
    diagnostics["post_scan_window_hours"] = post_window
    diagnostics["feed_scan_enabled"] = True
    diagnostics["hiring_posts_matched"] = len(report.hiring_posts)
    report.diagnostics = diagnostics
    return report
