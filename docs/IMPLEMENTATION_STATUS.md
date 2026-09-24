# Implementation status

## Current
- 12-skill registry
- Persistent Playwright context
- Centralized selector layer
- Session-state reader
- Initial LinkedIn job-search navigation
- Job preference model
- SQLite activity store
- Dry-run and approval gate

## Next
- Robust job-card extraction and pagination
- Profile extraction
- Company extraction
- People/recruiter extraction
- Content/post extraction
- Saved-post extraction
- Draft queues
- Scheduler
- Dashboard
- End-to-end browser tests

## Operational note
Real LinkedIn login must be performed by the account owner in a visible browser. No credentials or session cookies should be committed to the repository.
