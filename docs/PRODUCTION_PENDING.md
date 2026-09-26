# Production Pending

The repository's automated production gates are green. The remaining validation that cannot be performed in CI is an authenticated live-account smoke test on the operator's private Windows browser profile.

## Completed
- Complete-page job scrolling and post-scroll card re-location
- Job-card/detail-page field hydration, including posted time and location
- Strict India-scoped Delhi/Gurgaon/Noida/Jaipur filtering
- Strict configurable freshness filtering (default 1 hour)
- Title-family filtering, ranking and deduplication
- Recruiter/HR/hiring-manager discovery and draft generation
- Local application/history tracking
- Approval queue and action gateway
- 27-skill registry and deterministic skill tests
- End-to-end governed agent command
- Local control-center dashboard
- Read-only Windows hourly scheduler scripts
- Transient discovery retry/recovery
- CI compile, critical lint, dependency audit, secret scan, unit and browser-smoke gates

## Live operator validation
Run on the Windows machine with the private authenticated profile:
```powershell
python -m app release-check
python -m app agent-test --live
python -m app agent
```

The live run should report authenticated status and show eligible jobs when LinkedIn has postings matching the configured one-hour window. Zero results is valid when no eligible posting exists; inspect the emitted diagnostics rather than weakening the filters.

## Safety
- Manual LinkedIn login remains required.
- Passwords, OTPs, cookies and session tokens are never exported.
- CAPTCHA/security challenges remain user-handled.
- Consequential actions remain approval-gated.
- The scheduler is read-only and uses DRY_RUN=true.
- The dashboard binds to localhost by default.

## Remaining external dependency
The only release dependency is the operator's authenticated live-account validation. CI cannot substitute for a private LinkedIn session.
