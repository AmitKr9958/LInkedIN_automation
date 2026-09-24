# LinkedIn Automation Agent

A modular, local-first LinkedIn workflow assistant built with Python, Playwright, and an LLM adapter.

## Goals

- Persistent local browser profile for a user-controlled LinkedIn session
- Job discovery and structured filtering
- Profile/recruiter research
- Draft connection and follow-up messages
- Content drafting and scheduling
- Activity logging and analytics
- Human approval gates before consequential account actions
- Dry-run mode by default
- No credential/cookie exfiltration and no anti-detection or CAPTCHA bypass

> **Important:** LinkedIn's terms and platform policies can restrict automated interaction. Use this project only in ways permitted by LinkedIn and keep human approval enabled for account actions.

## Architecture

```
CLI / Scheduler
      |
      v
Orchestrator ---- LLM Provider
      |
      +---- Browser Adapter (Playwright)
      |
      +---- LinkedIn workflows
      |       +-- jobs
      |       +-- people
      |       +-- messages
      |       +-- content
      |
      +---- Approval Gate
      |
      +---- SQLite activity store
```

## Quick start

1. Python 3.11+
2. Node.js 20+ (Playwright browser tooling)
3. Create a virtual environment and install dependencies.
4. Install Chromium.
5. Copy `.env.example` to `.env`.
6. Run `python -m app login` and complete login manually in the visible browser.
7. Use `python -m app status` to verify the local profile.
8. Keep `DRY_RUN=true` while testing.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m playwright install chromium
python -m app --help
```

## Safety defaults

- DRY_RUN=true
- Human approval required for sending messages, connection requests, comments, posts and applications
- No automated CAPTCHA solving
- No stealth plugins or fingerprint spoofing
- Secrets stay in local environment variables
- Browser profile stays outside source control
