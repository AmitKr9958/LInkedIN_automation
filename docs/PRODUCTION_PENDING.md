# Production Pending

The repository's automated production gates are green. The remaining validation that cannot be performed in CI is an authenticated live-account smoke test on the operator's private Windows browser profile.

## Completed
- Complete-page job scrolling and post-scroll card re-location
- Job-card/detail-page field hydration, including posted time and location
- Strict India-scoped Delhi/Gurgaon/Noida/Jaipur filtering
- Strict configurable freshness filtering (default **48 hours**)
- Title-family filtering, ranking and deduplication
- Recruiter/HR/hiring-manager discovery and draft generation
- Local application/history tracking
- Approval queue and action gateway
- **28-skill** registry and deterministic skill tests
- End-to-end governed agent command
- Local control-center dashboard
- Read-only Windows hourly scheduler scripts using **`--max-posted-hours 48`**
- Exclusive agent file lock (prevents concurrent cycles)
- Last-run health status persistence (`data/last_run.json`)
- Scheduler log rotation under `data/logs/` (keeps newest 30 files)
- Transient discovery retry/recovery
- CI compile, critical lint, dependency audit, secret scan, unit and browser-smoke gates

## Live operator validation
Run on the Windows machine with the private authenticated profile:
```powershell
python -m app release-check
python -m app agent-test --live
python -m app agent
python -m app status
```

The live run should report authenticated status and show eligible jobs when LinkedIn has postings matching the configured **48-hour** window. Zero results is valid when no eligible posting exists; inspect the emitted diagnostics rather than weakening the filters.

## Scheduler (local Windows automatic mode)
```powershell
# Install (hourly, StartWhenAvailable, IgnoreNew, 20-minute timeout)
powershell -ExecutionPolicy Bypass -File scripts\install-readonly-scheduler.ps1

# Status / start / stop / uninstall
powershell -ExecutionPolicy Bypass -File scripts\scheduler-status.ps1
powershell -ExecutionPolicy Bypass -File scripts\scheduler-start.ps1
powershell -ExecutionPolicy Bypass -File scripts\scheduler-stop.ps1
powershell -ExecutionPolicy Bypass -File scripts\uninstall-readonly-scheduler.ps1
```

The scheduled runner uses:
- `.venv\Scripts\python.exe` when present
- `HEADLESS=true`
- `DRY_RUN=true`
- `--max-posted-hours 48`
- logs under `data\logs\agent-YYYYMMDD-HHMMSS.log`

**Limitation:** this is Local Windows automatic mode. The laptop must remain powered on and logged in for the task to run. True always-on 24×7 requires a separate always-on host (not implemented in this repository).

## Safety
- Manual LinkedIn login remains required.
- Passwords, OTPs, cookies and session tokens are never exported.
- CAPTCHA/security challenges remain user-handled.
- Consequential actions remain approval-gated.
- The scheduler is read-only and uses DRY_RUN=true.
- The dashboard binds to localhost by default.
- Concurrent agent cycles are blocked by `data/agent.lock`.

## Remaining external dependency
The only release dependency is the operator's authenticated live-account validation. CI cannot substitute for a private LinkedIn session.
