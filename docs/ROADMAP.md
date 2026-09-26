# Roadmap

## Phase 1 — Foundation
- [x] Repository initialized
- [x] Persistent Playwright profile
- [x] Environment configuration
- [x] Dry-run default
- [x] Approval gate
- [x] Activity database
- [x] CLI
- [x] Production release checks

## Phase 2 — LinkedIn read workflows
- [x] Session/login verification
- [x] Own profile reader
- [x] Job search reader
- [x] Job detail hydration/parser for missing card fields
- [x] Recruiter/profile research
- [ ] Notification reader

## Phase 3 — Drafting
- [x] Job-fit analysis
- [x] Recruiter message generator
- [x] Follow-up generator
- [x] Post generator
- [x] Comment generator
- [x] Connection-note generator

## Phase 4 — Controlled actions
- [x] Human approval queue
- [x] Publishing intent queue
- [x] Messaging intent queue
- [x] Connection-request intent queue
- [x] Follow-up intent queue
- [x] Saved-item read workflow

## Phase 5 — Operations
- [x] Retry/error recovery for transient discovery failures
- [x] Local dashboard
- [x] Read-only Windows hourly scheduler
- [x] Automated tests and browser smoke
- [x] Local release gate
- [ ] Authenticated live-account smoke test on each operator installation

## Explicit non-goals
- CAPTCHA bypass
- Fingerprint/stealth evasion
- Credential or session-cookie exfiltration
- Unbounded bulk messaging
- Unattended high-volume actions
- Automatic submission of consequential LinkedIn actions

The notification reader and live-account validation are the only intentionally open items. Consequential LinkedIn UI execution remains outside the autonomous agent boundary.
