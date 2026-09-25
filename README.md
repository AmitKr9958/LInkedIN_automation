# LinkedIn Automation Agent

A modular, local-first LinkedIn workflow assistant built with Python, Playwright, SQLite, and an optional LLM adapter.

## What this project does

The agent is designed as a **personal LinkedIn productivity control layer**:

- keeps a persistent browser profile on your own computer
- lets you log in manually once and reuse that local browser session
- verifies the session instead of assuming that a non-login URL means authentication
- discovers jobs, people, companies, posts, saved items and profile information
- identifies recruiter, HR and hiring-manager outreach targets for a job
- maintains a local Story Bank and content-quality audit layer
- normalizes job URLs and stores job/application history locally
- ranks jobs against your configured preferences
- drafts job-specific recruiter, HR, hiring-manager connection and follow-up messages
- keeps consequential account actions behind explicit approval
- tracks applications through a local lifecycle
- supports dry-run operation and CI/browser smoke tests
- never asks the agent to receive or export your password, OTP, cookies or session tokens

## Important LinkedIn limitation

LinkedIn's current User Agreement says members must not use unauthorized bots, scripts or other automated methods to scrape/copy the service or to automate actions such as adding contacts, sending/redirecting messages, or creating/liking/commenting/sharing posts. LinkedIn also states that third-party software that automates activity on its website is prohibited and may lead to account restrictions.

Therefore this repository **does not implement an unrestricted autonomous bot that takes over the account**. The safe architecture is:

**You own the browser session → agent reads/researches/drafts → you approve consequential actions → you perform or confirm the final LinkedIn action.**

I can continue extending the agent's read-only research, local intelligence, drafting, tracking, reporting, and approval workflow. I will not add CAPTCHA bypass, stealth/fingerprint evasion, cookie/session-token extraction, bulk unsolicited messaging, or uncontrolled automated engagement.

## Quick start

1. Install Python 3.11+.
2. Create and activate a virtual environment.
3. Install the project with development dependencies.
4. Install Chromium.
5. Copy `.env.example` to `.env`.
6. Keep `HEADLESS=false` for the first login.
7. Run `python -m app login` and log in yourself in the opened browser.
8. Close the browser normally after LinkedIn is signed in.
9. Run `python -m app status`.
10. Keep `DRY_RUN=true` while validating the workflow.

### Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m playwright install chromium
Copy-Item .env.example .env
python -m app login
python -m app status
```

## Useful commands

```text
python -m app skills
python -m app status
python -m app read profile
python -m app read jobs --query "Power BI" --location "Gurgaon"
python -m app read people --query "Power BI recruiter"
python -m app read companies --query "data analytics"
python -m app read posts --query "Power BI"
python -m app read saved

python -m app applications add "<job-url>" "Power BI Developer" "Company"
python -m app applications transition "<job-url>" shortlisted
python -m app applications transition "<job-url>" applied
python -m app applications list
python -m app applications list --status interview

python -m app approvals
python -m app approve <approval-id>
python -m app reject <approval-id>
```

## Your side: what is required

Only these setup steps are required from you:

1. **Install/run the project on your own Windows machine.**
2. **Log in to LinkedIn manually once** in the visible Playwright browser.
3. Complete any LinkedIn CAPTCHA, OTP or security challenge yourself if LinkedIn presents one.
4. Keep the local browser profile directory private and do not commit it.
5. Tell me the exact feature you want next if it requires a LinkedIn UI change; no password, OTP, cookie or `li_at` token is required.

The repository can then reuse the local browser profile without exporting credentials.

## Architecture

```text
CLI / local scheduler
        |
        v
Orchestrator ---- optional LLM provider
        |
        +---- Browser adapter (persistent local profile)
        |
        +---- Read/research skills
        |       +-- profile
        |       +-- jobs
        |       +-- people
        |       +-- companies
        |       +-- posts
        |       +-- saved
        |
        +---- Draft/approval skills
        |       +-- connections
        |       +-- messaging
        |       +-- engagement
        |       +-- followups
        |
        +---- Job intelligence + normalization
        |
        +---- Application tracker
        |
        +---- SQLite history / approval queue
```

## Current implementation status

All 27 skills are registered/governed. Their implementation boundaries are explicit:

- **Live read layer:** profile, jobs, people, companies, posts and saved items.
- **Content/intelligence layer:** 13 content/analysis skills plus the Story Bank.
- **Account/workflow layer:** authentication, connections, messaging, engagement, lead generation and follow-ups are governed workflow surfaces; consequential account-changing execution remains behind the approval gateway and is not an autonomous UI executor.

Application tracking, job normalization, discovery reporting, and JSON/CSV export are local and independent of LinkedIn.

## Testing

Unit tests are separated from browser smoke tests. CI installs Chromium for the smoke job and retains browser test artifacts on failure.

Run locally:

```powershell
pip install -e ".[dev]"
pytest -q -m "not e2e"
python -m playwright install chromium
pytest -q -m e2e --tracing=retain-on-failure
```

Do not put a real LinkedIn login/session into CI.

## Security model

- secrets stay local
- browser profile stays outside source control
- no password/OTP/cookie/session-token export
- no CAPTCHA solving
- no security/access-control bypass
- no stealth/fingerprint spoofing
- no bulk unsolicited messaging
- consequential actions require human approval
- read/runtime operations fail closed when the LinkedIn session cannot be verified

## Production hardening status

The repository now includes applicant-count metadata, experience parsing, explainable applicant/experience ranking signals, a complete 27-skill self-test contract, factual resume/job matching, factual resume tailoring, safe scheduled read-only discovery, notification providers, and PASS/WARN/FAIL smoke-test semantics. These features still require final automated and applicable live validation before a production-ready declaration.

Useful commands:

```text
python -m app monitor-jobs --once --query "Power BI Developer" --location "Gurgaon"
python -m app monitor-jobs --interval-minutes 1440 --query "Power BI Developer" --location "Gurgaon"
python -m app smoke-test --read-only
```

## Roadmap

The remaining engineering layers are release hardening rather than unrestricted account takeover:

- improve resilient selectors as LinkedIn UI changes
- harden resilient selectors and fixture coverage as LinkedIn UI changes
- add a local dashboard for jobs, applications and approvals
- complete live validation of applicant count, experience and all configured locations
- add a Windows scheduled **read-only** discovery workflow using the monitor command
- add optional user-confirmed browser handoff for individual actions

This keeps the tool useful for your job search while avoiding automation patterns that LinkedIn explicitly prohibits.

## New local quality and outreach commands

```text
python -m app selftest
python -m app audit-post --text "<draft>"
python -m app story-bank
python -m app story-bank --action search --query "Power BI"
python -m app add-story "Power BI automation" --metric "30%"
python -m app request-connection "Recruiter Name" "https://www.linkedin.com/in/example" --title "Recruiter" --company "Example"
python -m app request-followup "Recruiter Name" "https://www.linkedin.com/in/example" "Thanks for connecting..."
```

Connection/follow-up commands create controlled approval records. They do not claim that LinkedIn has completed the action.
