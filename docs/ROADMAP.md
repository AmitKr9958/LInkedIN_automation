# Roadmap

## Phase 1 — Foundation
- [x] Repository initialized
- [x] Persistent Playwright profile
- [x] Environment configuration
- [x] Dry-run default
- [x] Approval gate
- [x] Activity database
- [x] CLI

## Phase 2 — LinkedIn read workflows
- [x] Session/login verification
- [x] Own profile reader
- [x] Job search reader
- [ ] Job detail parser (job cards only today)
- [x] Recruiter/profile research
- [ ] Notification reader

## Phase 3 — Drafting
- [x] Job-fit analysis (preference-based ranking, including experience-range matching)
- [x] Recruiter message generator
- [x] Follow-up generator
- [x] Post generator
- [x] Comment generator
- [x] Connection-note generator

## Phase 4 — Controlled actions
- [x] Human approval queue
- [ ] Post publishing (queued drafts only; UI execution intentionally not implemented)
- [ ] Messaging (approval-gated surface; UI execution intentionally not implemented)
- [ ] Connection requests (approval-gated surface; UI execution intentionally not implemented)
- [ ] Saved-job workflows (saved-post reading only)

## Phase 5 — Operations
- [ ] Scheduler
- [ ] Dashboard
- [ ] Retry/error recovery
- [ ] Screenshots and audit trail
- [x] Automated tests (unit and browser smoke, split across CI jobs)
- [ ] Windows background runner

## Explicit non-goals
- CAPTCHA bypass
- Fingerprint/stealth evasion
- Credential or session-cookie exfiltration
- Unbounded bulk messaging
- Unattended high-volume actions that violate platform rules
