# Production Readiness

## Architecture

The project is divided into five boundaries:

1. Browser/session — persistent local Playwright profile owned by the user.
2. Research/intelligence — read operations, normalization, ranking, content analysis and application tracking.
3. Content quality — Post Audit, central Voice rules and persistent Story Bank.
4. Draft/approval — consequential actions enter the approval queue through ActionGateway.
5. Persistence/reporting — SQLite history, application lifecycle, approvals and JSON/CSV exports.

## Skill coverage

The registry currently contains **27** governed skills (verified by `python -m app selftest`).

### Account/workflow skills

- auth, profile, jobs, people, companies, posts, saved
- connections, messaging, engagement, leadgen, followups, outreach

### Content/intelligence skills

- post_writer, content_planner, comment_drafter, reply_handler
- post_audit, humanizer, hook_extractor, repurposer
- profile_optimizer, interviewer, story_bank
- engager_analytics, thread_monitor, employee_advocacy

## Release gates

Before a release is considered production-ready:

- `python -m compileall -q app tests`
- `ruff check app tests --select E9,F63,F7,F82`
- `pytest -q -m "not e2e"`
- Playwright browser smoke / E2E tests where applicable
- no secrets or local browser profile committed
- action gateway tests pass (queueing and per-run action-limit enforcement)
- policy tests pass
- application tracker tests pass
- Story Bank, outreach and self-test contract tests pass
- README/setup instructions are current
- no stale skill-count assertions or documentation remain
- **authenticated live job discovery smoke test on the operator machine**

## Operational rules

- Login is manual.
- The local browser profile is never exported.
- Credentials, OTPs and session cookies are never requested by the agent.
- CAPTCHA/security challenges are handled by the user.
- Consequential actions are approval-gated.
- Approval records are not treated as proof that LinkedIn completed an action.
- Bulk unsolicited messaging, security bypass and stealth/evasion are disabled.
- CI never receives a real LinkedIn session.

## Jobs pipeline (current)

```text
navigate → wait for cards → complete scroll → re-locate cards → parse all
→ optional bounded detail hydration → location filter → 48h freshness → return
```

Diagnostics are written to stderr as `read-diagnostics: {...}` for engineering visibility only (no secrets).

## Current status

**CODE COMPLETE — LIVE VALIDATION PENDING**

Automated release gates (compile, ruff critical, selftest, unit tests) pass. Live-account validation of job discovery must still be performed by the operator with their private authenticated browser profile. Until that succeeds with `final_returned > 0` for an eligible query, the product is not declared PRODUCTION READY.

## User setup later

No LinkedIn login is needed while developing the application layer.

When ready for browser integration:

1. Install dependencies and Chromium.
2. Run `python -m app doctor`.
3. Run `python -m app login`.
4. Log in manually.
5. Run `python -m app status` / `python -m app debug-auth`.
6. Start with read-only skills and validate selectors against the live account.
