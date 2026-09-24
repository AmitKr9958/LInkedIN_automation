from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_TRACKING_PREFIXES = ("trk", "tracking", "utm_")
_TRACKING_KEYS = {
    "ebp",
    "refid",
    "refId",
    "trackingid",
    "trackingId",
}


def normalize_job_url(url: str) -> str:
    if not url:
        return ""

    p = urlsplit(url)
    if not p.netloc:
        return url

    path = p.path.rstrip("/")
    # A LinkedIn job-view URL is uniquely identified by its path/job id.
    if "/jobs/view/" in path.lower():
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, "", ""))

    query = [
        (k, v)
        for k, v in parse_qsl(p.query)
        if not k.lower().startswith(_TRACKING_PREFIXES)
        and k not in _TRACKING_KEYS
    ]
    return urlunsplit(
        (p.scheme.lower(), p.netloc.lower(), path, "", urlencode(query))
    )


def dedupe_jobs(jobs: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []

    for index, job in enumerate(jobs):
        item = dict(job)
        raw_url = item.get("url") or item.get("href") or ""
        key = normalize_job_url(raw_url)

        if key:
            item["url"] = key
        else:
            fingerprint = "|".join(
                str(item.get(k, "")).strip().lower()
                for k in ("title", "company", "location")
            )
            # Do not collapse completely empty records into one another.
            key = fingerprint if fingerprint.strip("|") else f"__empty__{index}"

        if key in seen:
            continue

        seen.add(key)
        out.append(item)

    return out
