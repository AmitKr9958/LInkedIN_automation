# Implementation status

## Current

### Platform
- Python 3.11+ project configuration
- Persistent Playwright Chromium context
- Centralized LinkedIn selector layer
- Conservative LinkedIn session-state verification
- SQLite activity/history store
- Dry-run and human approval gate
- CLI entry point and production-readiness doctor

### LinkedIn read layer
- Profile extraction with rendered-page fallbacks
- Job search and job-card extraction with selector fallbacks
- Job-card deduplication by canonical LinkedIn job URL
- People/recruiter search
- Company search
- Post/content search
- Saved-post extraction

### Job intelligence
- Job preference model
- LinkedIn job URL normalization
- Preference-based job ranking
- Local job history and discovery reporting
- JSON/CSV application export

### Application management
- Application lifecycle tracking
- Status transition validation
- Approval queue with SQLite persistence
- Legacy approval-queue schema migration

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
- duplicate rendered job-title cleanup
- canonical LinkedIn job URL normalization
- regression tests for these cases

The next required release validation is to pull the latest `main` commit and rerun the live read commands, followed by the local unit/E2E suite.

## Operational note

Real LinkedIn login must be performed by the account owner in a visible browser. No credentials, OTPs, cookies or session tokens should be committed to the repository. Consequential LinkedIn actions remain governed by the approval gateway and are not autonomous UI executors.