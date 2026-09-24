# Implementation status

## Current

### Platform
- Python 3.11+ project configuration
- Persistent Playwright Chromium context
- Centralized LinkedIn selector layer
- Conservative LinkedIn session-state verification
- SQLite activity/history store
- Dry-run and human approval gate with enforced per-run action limit
- CLI entry point and production-readiness doctor

### LinkedIn read layer
- Profile extraction with rendered-page fallbacks
- Job search and job-card extraction with selector fallbacks
- Job-card deduplication by canonical LinkedIn job URL
- People/recruiter search
- Company search
- Post/content search
- Saved-post extraction with permalink capture
- Result deduplication for people, company, post and saved reads (shared parsing helper)

### Job intelligence
- Job preference model
- LinkedIn job URL normalization
- Preference-based job ranking
- Robust posted-time extraction (card text, aria-label/title/datetime attributes, time elements, JSON-LD, detail-page main-text fallback)
- Hour-level relative-time precision from datetime values plus numeric `posted_hours` recency for 48-hour filtering
- Company extraction hardening (selectors, logo-alt, accessibility attributes, detail-page company link, page-title and JSON-LD fallbacks, noise-line filtering, placeholder-card skip)
- Targeted job-detail hydration for records missing company/posted (capped at 10 per run; card values always win the merge)
- Extraction-source debug diagnostics (`card`/`detail-page`/`missing`) that never log credentials or session data
- Experience-range matching against configured minimum/maximum years
- Discovery-report job persistence fix (ranked dict records)
- Local job history and discovery reporting (`python -m app history`)
- JSON/CSV application export

### Application management
- Application lifecycle tracking
- Status transition validation
- Approval queue with SQLite persistence
- Legacy approval-queue schema migration
- Local activity log for approval requests/decisions and discovery runs
- Follow-up lifecycle records (create, list, duplicate-safe, validated status transitions)

### Skills
- 24 registered/governed skills
- 6 live read skills: profile, jobs, people, companies, posts, saved
- 12 content/intelligence skills implemented locally
- 6 account/workflow skills remain approval-gated workflow surfaces rather than autonomous UI executors

## Validation

The codebase has automated release gates for:
- Python compilation
- Ruff syntax/error checks
- Non-E2E unit tests
- Playwright browser smoke tests

The latest previously validated CI commit passed both the unit and browser-smoke jobs. The reader-hardening commits made after that validation must be run through CI before the next release is called fully production-ready.

## Live-account validation

The authenticated local browser session has been validated on the user's Windows machine:
- `python -m app status` reports an authenticated LinkedIn feed.
- `python -m app debug-auth` reports the persistent browser profile and authenticated feed.
- `python -m app read profile` reaches the authenticated profile page.
- `python -m app read jobs --query "Power BI" --location "Gurgaon"` reaches current LinkedIn job results.

The latest live test exposed profile-field and job-card extraction defects. Reader hardening has been added for:
- rendered profile fields and title fallback
- stable job-card selector fallback order
- duplicate job-card suppression
- duplicate rendered job-title cleanup (including no-separator concatenated titles)
- robust posted-time extraction (time element text, datetime fallback, "within the past 24 hours" suffix normalization, no badge leakage)
- company extraction hardening (logo-alt fallback, alumni/state noise filtering, unhydrated placeholder cards skipped)
- live job-detail fallback: when a search card lacks company or posted (the 2026 result cards usually omit posted time), the detail page is hydrated for just those records (max 10 per run) and merged without overwriting card values
- posted labels now resolve from the detail page's top-card region when cards omit them, and every record carries numeric `posted_hours` for 48-hour filtering
- lazy job-card hydration (scrolling so cards render their full contents)
- canonical LinkedIn job URL normalization
- regression tests for these cases

Release validation has been rerun against the current working tree: the local unit/E2E suite passes (97 tests) warning-free (pytest-asyncio 1.x on Python 3.14), `python -m app doctor` reports all checks green, and live validation (`status` plus a Power BI/Gurgaon job search) confirmed an authenticated session, clean job-card extraction, correct 48-hour recency filtering, and full posted-time coverage after the extraction hardening: 7/7 live records now carry both `posted` and `posted_hours` ("1 hour ago" = 1.0, "23 hours ago" = 23.0, "2 days ago" = 48.0, "1 week ago" = 168.0) and company is populated wherever LinkedIn exposes it. A promoted posting that LinkedIn renders without any structured company (no company link, logo alt, JSON-LD or metadata — the name appears only inside description prose) intentionally stays `""` as explicitly unknown.

## Operational note

Real LinkedIn login must be performed by the account owner in a visible browser. No credentials, OTPs, cookies or session tokens should be committed to the repository. Consequential LinkedIn actions remain governed by the approval gateway and are not autonomous UI executors.