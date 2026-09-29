# 24×7 Operations Guide

This document describes how to run the LinkedIn automation agent in **local Windows automatic mode** on an always-on Windows host. It is **not** a cloud-hosted multi-tenant service.

## 1. Architecture

```
LinkedIn account
    ↓
Persistent local browser profile (.browser-profile)
    ↓
Authenticated Playwright session (manual login)
    ↓
Read-only discovery / intelligence
    ↓
Filtering / ranking / deduplication (4h, locations, title family)
    ↓
Local persistence / reporting (SQLite, last_run.json, logs)
    ↓
Health / monitoring
    ↓
Human approval for consequential actions (ActionGateway)
```

No autonomous account-changing activity is performed by the scheduler.

## 2. Host requirements

| Requirement | Notes |
|-------------|-------|
| OS | Windows 10/11 or Windows Server with Task Scheduler |
| Power | Machine must stay powered on (or use a VM that does) |
| Logon | Interactive user session recommended if the persistent Chromium profile requires it |
| Python | 3.11+ with project `.venv` |
| Playwright | Chromium installed via `python -m playwright install chromium` |
| Network | Outbound HTTPS to linkedin.com |
| Disk | Persistent `.browser-profile` and `data/` directory |
| Scheduler | Windows Task Scheduler enabled |

**True always-on 24×7** requires a dedicated always-on host or VM. A laptop that sleeps or logs off will miss cycles.

## 3. Installation

```powershell
cd "E:\LinkedIn Automation"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m playwright install chromium
```

## 4. Authentication setup

```powershell
# Visible browser — complete LinkedIn login (including MFA/CAPTCHA) manually
$env:HEADLESS="false"
python -m app login
python -m app debug-auth   # must report authenticated
```

Never put passwords, OTPs, or session tokens in env files or scripts.

## 5. Scheduler setup

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-readonly-scheduler.ps1
powershell -ExecutionPolicy Bypass -File scripts\scheduler-status.ps1
```

Configured behavior:
- 2-hour repetition (recommended post-restriction cadence)
- `StartWhenAvailable`
- Hidden (wscript → VBS → PowerShell `-WindowStyle Hidden`)
- `MultipleInstances = IgnoreNew` (plus in-process `data/agent.lock`)
- `ExecutionTimeLimit = 45 minutes` (exceeds measured worst-case cycle)
- `HEADLESS=true`, `DRY_RUN=true`, `--max-posted-hours 4`

## 6. Health checks

```powershell
python -m app status
# Inspect data\last_run.json
# health_state: HEALTHY | DEGRADED | FAILED | AUTH_REQUIRED | STALE | NEVER_RUN
```

Key fields: `last_status`, `health_state`, `consecutive_failures`, `failure_type`, `last_success_at`, `last_duration_seconds`.

## 7. Log locations

- `data\logs\agent-YYYYMMDD-HHMMSS.log` — rotated (newest 30 kept)
- Cycle markers: `agent cycle start` / `agent cycle end exit=N duration=...s`

## 8. Failure recovery

| Condition | Behavior |
|-----------|----------|
| Transient navigation timeout | Bounded retry (2 attempts) with backoff |
| Auth expired | Fail closed, `failure_type=auth_required`, operator must re-login |
| Chromium missing | Fail closed, `browser_unavailable` |
| Profile locked | Fail closed, `profile_locked` — close other Chromium using the profile |
| All locations infrastructure-fail | Fail closed (not success-empty) |
| Zero matching jobs | Success with `jobs=0` when infrastructure and auth are OK |

## 9. Authentication recovery

1. `python -m app status` → `AUTH_REQUIRED` or auth error in log
2. `$env:HEADLESS="false"; python -m app login`
3. Complete LinkedIn challenges manually
4. `python -m app debug-auth`
5. Next scheduled cycle recovers automatically

## 10. Windows restart behavior

After reboot:
- Task remains registered and enabled
- Next trigger (or `StartWhenAvailable`) runs the hidden launcher
- Working directory is the repository root (from VBS/PowerShell)
- Browser profile path is relative to the repo

If Windows requires interactive logon for the profile, document that the host must auto-logon or remain logged in.

## 11. Profile-lock recovery

If another process holds `.browser-profile`:
- Close orphan Chromium/agent windows
- Or wait for `STALE_SECONDS` (50 minutes) so the lock file can be reclaimed
- Do not delete the profile directory

## 12. Uninstall

```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall-readonly-scheduler.ps1
```

## 13. Backup considerations

Back up (offline, encrypted if possible):
- `data/` (SQLite, approvals, history) — no secrets by design
- Not the live `.browser-profile` unless encrypted and offline only

Do not upload LinkedIn session data to cloud services.

## 14. Security considerations

- `.browser-profile`, `.env`, cookies, tokens never committed
- Scheduler runs DRY_RUN=true (read-only)
- ActionGateway remains the sole path for consequential actions
- Logs must not contain passwords/OTPs/cookies

## 15. Known LinkedIn limitations

- Selectors and page structure change; monitor `selector_health` / diagnostics
- Rate limits and security challenges require human response
- Read-only automation still must respect LinkedIn terms

## 16. What requires manual intervention

- Initial and re-authentication
- CAPTCHA / MFA / checkpoint
- Approving connection/message/publish actions
- Resolving a permanently locked profile
- Host power/network outages

## 17. How to verify the system is healthy

```powershell
python -m app debug-auth          # authenticated
python -m app status              # health_state HEALTHY, recent last_success_at
powershell -ExecutionPolicy Bypass -File scripts\scheduler-status.ps1
# Recent data\logs\agent-*.log contains "agent cycle end exit=0"
# data\last_run.json last_status=success, consecutive_failures=0
```
