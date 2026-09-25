# Production Readiness

## Current architecture
1. Persistent local browser/session boundary.
2. Read/research and job-intelligence boundary.
3. Content/voice/story quality boundary.
4. Approval gateway for consequential actions.
5. SQLite history/application/approval/reporting boundary.
6. Safe scheduler and notification-provider boundary.

## 27 skills
The registry contains exactly 27 governed skills. The self-test now checks the complete expected set rather than only content dispatch.

## Implemented
- authenticated local browser
- profile/jobs/people/companies/posts/saved reads
- job normalization, deduplication and history
- 48-hour freshness
- configurable applicant-count signals
- experience metadata parsing and explainable ranking
- recruiter/HR/hiring-manager outreach planning
- follow-up lifecycle
- application tracking and event audit history
- Post Audit, Voice Engine, Humanizer, Story Bank and content skills
- resume/job matching and factual resume tailoring
- optional console/file/email notification providers
- safe read-only scheduler
- smoke-test PASS/WARN/FAIL semantics

## Not yet proven production-ready
- live applicant-count coverage across current LinkedIn UI
- all four location live matrix cases
- live experience coverage
- end-to-end outreach/application workflow
- actual provider-backed media generation
- actual LinkedIn publishing
- real application form submission
- continuous scheduler operation on the user's machine
- GitHub Actions result for the final hardened revision
- full security/secret-scan release evidence

## Safety
DRY_RUN=true and APPROVAL_REQUIRED=true remain the defaults. No credential/session export, CAPTCHA/MFA bypass, stealth evasion or uncontrolled bulk account actions are implemented.

## Release gate
Do not label the project production-ready until automated tests, selftest, doctor, CI and applicable live read-only gates have all passed and documentation matches the implementation.
