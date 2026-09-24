# Production Readiness

## Architecture

The project is divided into four boundaries:

1. Browser/session — persistent local Playwright profile owned by the user.
2. Research/intelligence — read operations, normalization, ranking, content analysis and application tracking.
3. Draft/approval — every consequential action enters the approval queue through ActionGateway.
4. Persistence/reporting — SQLite history, application lifecycle, approvals and JSON/CSV exports.

## Skill coverage

### Account/workflow skills
- auth
- profile
- jobs
- people
- companies
- posts
- saved
- connections
- messaging
- engagement
- leadgen
- followups

### Content/intelligence skills
- post_writer
- content_planner
- comment_drafter
- reply_handler
- humanizer
- hook_extractor
- repurposer
- profile_optimizer
- interviewer
- engager_analytics
- thread_monitor
- employee_advocacy

## Release gates

Before a release is considered production-ready:

- python -m compileall -q app tests
- ruff check app tests --select E9,F63,F7,F82
- pytest -q -m "not e2e"
- Playwright browser smoke tests pass
- no secrets or local browser profile committed
- action gateway tests pass
- policy tests pass
- application tracker tests pass
- README/setup instructions are current

## Operational rules

- Login is manual.
- The local browser profile is never exported.
- Credentials, OTPs and session cookies are never requested by the agent.
- CAPTCHA/security challenges are handled by the user.
- Consequential actions are approval-gated.
- Bulk unsolicited messaging, security bypass and stealth/evasion are disabled.
- CI never receives a real LinkedIn session.

## User setup later

No LinkedIn login is needed while developing the application layer.

When ready for browser integration:

1. Install dependencies and Chromium.
2. Run `python -m app doctor`.
3. Run `python -m app login`.
4. Log in manually.
5. Run `python -m app status`.
6. Start with read-only skills and validate selectors against the live account.
