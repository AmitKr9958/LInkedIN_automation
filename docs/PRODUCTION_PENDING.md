# LinkedIn Automation Agent — Current Issues & Pending Work

## 1. Current Status

**CODE COMPLETE — LIVE VALIDATION PENDING**

The automated codebase is healthy:

- **156 automated unit tests pass** (`pytest -q -m "not e2e"`)
- **27 skills are registered and self-test successfully**
- `compileall` and `ruff` (critical rules) pass
- Complete-page scrolling, all-card parsing, 48-hour freshness, location normalization, and deduplication are implemented with regression coverage
- Safe pipeline diagnostics are emitted for every jobs search stage

The primary remaining gate is **authenticated live LinkedIn validation** on the operator's local machine (persistent browser profile). CI intentionally never receives a real LinkedIn session.

```powershell
python -m app debug-auth
python -m app read profile
python -m app read jobs --query "Power BI Developer" --location "Gurgaon"
```

Until that live smoke test returns non-empty eligible jobs with correct diagnostics, the project must not be declared **PRODUCTION READY**.

---

# 2. COMPLETED (code / automated)

| Area | Status |
|------|--------|
| Complete LinkedIn jobs-page scrolling (`_scroll_complete_results_page`) | Done + regression test |
| Re-locate cards **after** scroll (no stale pre-scroll snapshot) | Done |
| No hidden 50-job parser limit | Confirmed removed |
| All currently loaded cards parsed | Done |
| Posted-time extraction (card + detail hydration, relative patterns) | Done + unit tests |
| 48-hour freshness filter (default; unknown age rejected) | Done + unit tests |
| Location normalization (Gurgaon↔Gurugram, Delhi↔New Delhi, token-based) | Done + unit tests |
| Deduplication by normalized job URL | Done + unit tests |
| Bounded detail-page hydration (`MAX_DETAIL_HYDRATION = 10`) | Done |
| Safe stage diagnostics (scroll, cards, fields, freshness, location, duplicates) | Done |
| Syntax defect in scroll loop (`let` JS leak) | Fixed |
| Auth fail-closed when session not verified | Done |
| DRY_RUN / approval gates / no CAPTCHA bypass / no secret export | Preserved |

---

# 3. PRIMARY BLOCKER — LIVE AUTHENTICATED JOB DISCOVERY

Previous live probes showed job cards present in the DOM (`[data-occludable-job-id]`, `.job-card-container`, `/jobs/view/` links) while:

```text
python -m app read jobs --query "Power BI Developer" --location "Gurgaon"
→ []
```

Root causes addressed in code:

1. **Scroll function was not valid Python** (`let previous = None`) — fixed; module now compiles.
2. Cards were located **before** scroll and not always re-queried after infinite load — fixed: locate → scroll → **re-locate** → parse.
3. Fallback locator preferred bare `<a>` links (missing sibling metadata) — fixed: prefer `li`/`article` ancestors of job links.
4. Diagnostics were incomplete — expanded to stage counters so live runs can show exactly where records are dropped.

**Still required from the operator:**

1. Authenticated local session (`python -m app login` once, profile private).
2. Run the three live commands above and inspect `read-diagnostics:` on stderr.
3. Confirm `final_returned > 0` when eligible jobs exist on LinkedIn for the query/location/48h window.

---

# 4. LIVE DIAGNOSTICS TO VERIFY

On a successful live run, diagnostics should include (names may also appear as aliases):

```text
scroll_passes
scroll_completed
scroll_max_height
scroll_job_count

cards_detected
cards_parsed
cards_missing_title / company / location / url / posted

urls_extracted / titles_extracted / companies_extracted
locations_extracted / posted_extracted

detail_pages_visited
*_filled_from_detail

location_candidates / location_rejected / rejected_location
duplicate_count / rejected_duplicate

freshness_window_hours
freshness_candidates / freshness_rejected / rejected_freshness
unknown_age_count / unknown_posted_age
returned_after_freshness
final_returned
```

Diagnostics must never contain passwords, cookies, session tokens, or authorization headers.

---

# 5. LOCATION FILTERING

Supported (token / alias normalized):

- Delhi ↔ New Delhi
- Gurgaon ↔ Gurugram
- Noida, Jaipur (when present on the card)

Rules:

- Gurugram matches Gurgaon
- New Delhi matches Delhi
- Noida does **not** match Gurgaon
- India-only Remote does **not** match Gurgaon/Delhi
- US Remote does **not** match Delhi
- Explicit "Gurgaon + Remote" may match Gurgaon

Unit tests: `tests/test_job_location_filter.py`, reader hardening.

**Pending:** live confirmation only.

---

# 6. 48-HOUR FRESHNESS

Default: `max_posted_hours = 48` (`DEFAULT_JOB_PREFERENCES.posted_within_hours`).

| Age | Default |
|-----|---------|
| ≤ 48 hours | include |
| > 48 hours | exclude |
| unknown (`posted_hours is None`) | exclude |
| `--max-posted-hours -1` | disable filter |

Override / include-unknown via CLI kwargs. Unit tests: `tests/test_job_freshness.py`.

**Pending:** live confirmation that posted times are extracted from the current LinkedIn DOM so the filter is not starving results solely due to missing ages.

---

# 7. DEDUPLICATION

Canonical identity: normalized LinkedIn job URL (`normalize_job_url`). Tracking/query params stripped. Same job after scroll counted once (`duplicate_count`).

---

# 8. SAFETY / SECURITY (unchanged)

- DRY_RUN default
- Approval gates for consequential actions
- No password / OTP / cookie / session export
- No CAPTCHA or access-control bypass
- No stealth/evasion
- No real LinkedIn session in CI
- Browser profile stays local and private

---

# 9. TESTING GATES

```text
python -m compileall -q app tests
ruff check app tests --select E9,F63,F7,F82
python -m app selftest
pytest -q -m "not e2e"
pytest -q tests/test_job_freshness.py
pytest -q tests/test_reader_hardening.py
pytest -q -m e2e --tracing=retain-on-failure   # no real session in CI
```

---

# 10. WHAT IS NOT DONE

1. **Authenticated live LinkedIn smoke test** on the operator machine (must show non-empty jobs when LinkedIn has eligible results).
2. Closing related GitHub issues only after live confirmation.
3. Optional: broader live fixture capture if LinkedIn DOM changes again.

Repository hygiene (committed probe artifacts and operational sample application exports) has been cleaned; `.gitignore` now excludes local SQLite, exports, caches, and scratch files.

Until (1) succeeds, status remains:

```text
CODE COMPLETE — LIVE VALIDATION PENDING
```
