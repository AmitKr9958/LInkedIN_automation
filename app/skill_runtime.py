from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .browser import linkedin_browser
from .job_preferences import DEFAULT_JOB_PREFERENCES
from .linkedin_reader import current_session_state
from .skills import companies, jobs, notifications, people, posts, profile, saved


@dataclass
class RuntimeResult:
    skill: str
    data: Any
    diagnostics: dict | None = None



def _normalize_job_title(value: str) -> str:
    import re
    normalized = (value or "").lower().replace("–", "-").replace("—", "-")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _job_title_matches_preferences(
    title: str,
    job_text: str = "",
    keywords: list[str] | None = None,
) -> bool:
    """Match the configured target job families without accepting unrelated managers."""
    import re
    title_norm = _normalize_job_title(title)
    if not title_norm:
        return False
    configured = keywords or DEFAULT_JOB_PREFERENCES.keywords
    for keyword in configured:
        if _normalize_job_title(keyword) in title_norm:
            return True

    leadership_terms = ("lead", "manager", "assistant manager", "senior manager")
    domain_patterns = (
        r"\bpower bi\b",
        r"\bbusiness intelligence\b",
        r"\bbi\b",
        r"\bdata\b",
        r"\banalytics\b",
        r"\breporting\b",
        r"\bmis\b",
    )
    if any(term in title_norm for term in leadership_terms):
        if any(re.search(pattern, title_norm) for pattern in domain_patterns):
            return True
    text_norm = _normalize_job_title(job_text)
    if "assistant manager" in title_norm and any(
        re.search(pattern, text_norm) for pattern in domain_patterns
    ):
        return True
    return False


def _filter_jobs_by_preference_exclusions(
    data: list[Any],
    diagnostics: dict | None = None,
) -> list[Any]:
    """Reject jobs that violate the configured internship/fresher policy."""
    import re
    kept: list[Any] = []
    rejected_internship = 0
    rejected_fresher = 0
    samples: list[dict[str, Any]] = []

    internship_patterns = (
        r"\bintern(ship)?\b",
        r"\binterns\b",
        r"\btrainee\b",
    )
    fresher_patterns = (
        r"\bfresher\b",
        r"\bentry[- ]level\b",
        r"\b0\s*[-–]?\s*1\s*(?:year|yr|years|yrs)?\b",
        r"\b0\s*(?:year|yr|years|yrs)\b",
        r"\b1\s*(?:year|yr|years|yrs)\b",
    )

    for job in data:
        title = str(getattr(job, "title", "") or "")
        text = str(getattr(job, "text", "") or "")
        evidence = _normalize_job_title(f"{title} {text}")
        if DEFAULT_JOB_PREFERENCES.exclude_internships and any(re.search(p, evidence) for p in internship_patterns):
            rejected_internship += 1
            if len(samples) < 5:
                samples.append({"title": title[:120], "company": str(getattr(job, "company", "") or "")[:120], "reason": "internship"})
            continue
        if DEFAULT_JOB_PREFERENCES.exclude_fresher_roles and any(re.search(p, evidence) for p in fresher_patterns):
            rejected_fresher += 1
            if len(samples) < 5:
                samples.append({"title": title[:120], "company": str(getattr(job, "company", "") or "")[:120], "reason": "fresher"})
            continue
        kept.append(job)

    if diagnostics is not None:
        diagnostics["preference_exclusion_enabled"] = True
        diagnostics["rejected_internship"] = rejected_internship
        diagnostics["rejected_fresher"] = rejected_fresher
        diagnostics["preference_rejection_samples"] = samples
        diagnostics["returned_after_preference_exclusions"] = len(kept)
    return kept


def _filter_jobs_by_title(
    data: list[Any],
    keywords: list[str] | None = None,
    diagnostics: dict | None = None,
) -> list[Any]:
    kept: list[Any] = []
    rejected = 0
    samples: list[dict[str, Any]] = []
    for job in data:
        title = str(getattr(job, "title", "") or "")
        text_value = str(getattr(job, "text", "") or "")
        if _job_title_matches_preferences(title, text_value, keywords):
            kept.append(job)
        else:
            rejected += 1
            if len(samples) < 5:
                samples.append({
                    "title": title[:120],
                    "company": str(getattr(job, "company", "") or "")[:120],
                })
    if diagnostics is not None:
        diagnostics["title_filter_enabled"] = True
        diagnostics["title_candidates"] = len(data)
        diagnostics["rejected_title"] = rejected
        diagnostics["returned_after_title"] = len(kept)
        diagnostics["title_rejection_samples"] = samples
    return kept


def _filter_posts_by_freshness(
    data: list[Any],
    max_posted_hours: float | None = 48,
    diagnostics: dict | None = None,
) -> list[Any]:
    """Keep only posts whose parsed age is within the configured window."""
    if max_posted_hours is None:
        if diagnostics is not None:
            diagnostics["post_freshness_window_hours"] = None
        return data
    kept: list[Any] = []
    unknown = 0
    rejected = 0
    for post in data:
        age = getattr(post, "posted_hours", None)
        if age is None:
            unknown += 1
            continue
        if age <= max_posted_hours:
            kept.append(post)
        else:
            rejected += 1
    if diagnostics is not None:
        diagnostics["post_freshness_window_hours"] = max_posted_hours
        diagnostics["post_freshness_candidates"] = len(data)
        diagnostics["post_freshness_rejected"] = rejected
        diagnostics["post_unknown_age"] = unknown
        diagnostics["post_returned_after_freshness"] = len(kept)
    return kept


def _filter_jobs_by_freshness(
    data: list[Any],
    max_posted_hours: float | None = 48,
    diagnostics: dict | None = None,
    *,
    include_unknown_age: bool = False,
) -> list[Any]:
    """Apply a maximum posting-age window.

    When ``max_posted_hours`` is None, no freshness filter is applied.

    When a window is active:
    - Jobs with ``posted_hours`` <= window are kept.
    - Jobs with ``posted_hours`` > window are rejected.
    - Jobs with unknown age (``posted_hours is None``) are excluded by
      default (strict job-alert policy). Set ``include_unknown_age=True``
      to keep them instead.
    """
    if max_posted_hours is None:
        if diagnostics is not None:
            diagnostics["freshness_window_hours"] = None
        return data
    kept: list[Any] = []
    rejected = 0
    unknown = 0
    rejection_samples: list[dict[str, Any]] = []
    unknown_samples: list[dict[str, Any]] = []

    def _sample(job: Any) -> dict[str, Any]:
        return {
            "title": str(getattr(job, "title", "") or "")[:120],
            "company": str(getattr(job, "company", "") or "")[:120],
            "location": str(getattr(job, "location", "") or "")[:160],
            "posted": str(getattr(job, "posted", "") or "")[:80],
            "posted_hours": getattr(job, "posted_hours", None),
            "href": str(getattr(job, "href", "") or "")[:240],
        }

    for job in data:
        age = getattr(job, "posted_hours", None)
        if age is None:
            unknown += 1
            if len(unknown_samples) < 5:
                unknown_samples.append(_sample(job))
            if include_unknown_age:
                kept.append(job)
            else:
                rejected += 1
            continue
        if age <= max_posted_hours:
            kept.append(job)
        else:
            rejected += 1
            if len(rejection_samples) < 5:
                rejection_samples.append(_sample(job))
    if diagnostics is not None:
        diagnostics["freshness_window_hours"] = max_posted_hours
        diagnostics["rejected_freshness"] = rejected
        diagnostics["freshness_rejected"] = rejected
        diagnostics["unknown_posted_age"] = unknown
        diagnostics["unknown_age_count"] = unknown
        diagnostics["freshness_candidates"] = len(data)
        diagnostics["returned_after_freshness"] = len(kept)
        diagnostics["final_returned"] = len(kept)
        diagnostics["include_unknown_age"] = include_unknown_age
        diagnostics["freshness_rejection_samples"] = rejection_samples
        diagnostics["unknown_age_samples"] = unknown_samples
    return kept


async def ensure_authenticated(page, *, settle_ms: int = 5_000, attempts: int = 3) -> dict:
    """Navigate to the feed and verify the local session is authenticated.

    Retries briefly because persistent-profile cookie restore can lag on the
    first headless launch after a headed login. Never bypasses LinkedIn login
    or security challenges — fails closed when the session is not verified.
    """
    last_state: dict = {}
    for attempt in range(1, attempts + 1):
        try:
            await page.goto(
                "https://www.linkedin.com/feed/",
                wait_until="domcontentloaded",
                timeout=60_000,
            )
        except Exception:
            if attempt >= attempts:
                raise
            await page.wait_for_timeout(2_000 * attempt)
            continue
        await page.wait_for_timeout(settle_ms if attempt == 1 else 2_000)
        last_state = await current_session_state(page)
        if last_state.get("authenticated"):
            return last_state
        # Soft retry: LinkedIn sometimes shows an interstitial before the feed.
        await page.wait_for_timeout(2_000 * attempt)
    raise RuntimeError(
        "LinkedIn session is not verified. Run 'python -m app login' "
        "with HEADLESS=false and sign in manually. "
        f"Last page: url={last_state.get('url', '')!r} "
        f"title={last_state.get('title', '')!r} "
        f"confidence={last_state.get('confidence', '')!r}."
    )


async def run_read_on_page(page, skill: str, **kwargs) -> RuntimeResult:
    """Execute a read skill on an already-open authenticated page.

    Used by the agent cycle so the persistent profile is opened once per
    cycle instead of once per location/query (faster and more reliable).
    """
    if skill == "profile":
        data = await profile.read_profile(page)
    elif skill == "jobs":
        diagnostics: dict = {"skill": "jobs"}
        window = (
            kwargs["max_posted_hours"]
            if "max_posted_hours" in kwargs
            else float(DEFAULT_JOB_PREFERENCES.posted_within_hours)
        )
        data = await jobs.search(
            page,
            kwargs.get("keywords", DEFAULT_JOB_PREFERENCES.keywords[0]),
            kwargs.get("location", "Gurgaon"),
            start=kwargs.get("start", 0),
            diagnostics=diagnostics,
            max_posted_hours=window,
        )
        data = _filter_jobs_by_title(
            data,
            DEFAULT_JOB_PREFERENCES.keywords,
            diagnostics=diagnostics,
        )
        data = _filter_jobs_by_preference_exclusions(
            data,
            diagnostics=diagnostics,
        )
        data = _filter_jobs_by_freshness(
            data,
            window,
            diagnostics=diagnostics,
            include_unknown_age=bool(kwargs.get("include_unknown_age", False)),
        )
        if not data and diagnostics is not None:
            loc = kwargs.get("location") or diagnostics.get("requested_location") or ""
            diagnostics.setdefault(
                "zero_result_reason",
                (
                    f"No qualifying {loc} jobs found within the configured "
                    f"{window}-hour freshness window "
                    "(unknown posting ages remain excluded by default)."
                    if loc
                    else (
                        f"No qualifying jobs found within the configured "
                        f"{window}-hour freshness window "
                        "(unknown posting ages remain excluded by default)."
                    )
                ),
            )
        return RuntimeResult(skill, data, diagnostics)
    elif skill == "people":
        data = await people.search(
            page,
            kwargs.get("query", "Power BI recruiter"),
            kwargs.get("location", ""),
        )
    elif skill == "companies":
        data = await companies.search(page, kwargs.get("query", "technology"))
    elif skill == "posts":
        diagnostics = {}
        if kwargs.get("feed", False):
            data = await posts.read_feed(
                page,
                max_scrolls=int(kwargs.get("max_scrolls", 6)),
            )
        else:
            data = await posts.search(page, kwargs.get("query", "Power BI"))
        data = _filter_posts_by_freshness(
            data,
            kwargs.get("max_posted_hours", 48),
            diagnostics=diagnostics,
        )
        if hasattr(data, "to_dict"):
            data = data.to_dict()
        elif isinstance(data, list):
            data = [x.to_dict() if hasattr(x, "to_dict") else x for x in data]
        return RuntimeResult(skill, data, diagnostics)
    elif skill == "saved":
        data = await saved.read_saved_posts(page)
    elif skill == "notifications":
        data = await notifications.search(page)
    else:
        raise ValueError(f"Unsupported read skill: {skill}")

    if hasattr(data, "to_dict"):
        data = data.to_dict()
    elif isinstance(data, list):
        data = [x.to_dict() if hasattr(x, "to_dict") else x for x in data]
    return RuntimeResult(skill, data)


async def run_read(skill: str, **kwargs) -> RuntimeResult:
    """Open one persistent profile, verify auth, run one read skill, then close.

    Callers that need multiple searches should prefer run_read_on_page() inside
    one linkedin_browser() context so the persistent profile is opened once.
    """
    async with linkedin_browser() as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()
        await ensure_authenticated(page)
        return await run_read_on_page(page, skill, **kwargs)
