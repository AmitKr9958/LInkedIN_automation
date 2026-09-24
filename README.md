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


## Current implementation

All 12 skill modules are now present. The first operational layer is read-only: profile, jobs, people, companies, posts and saved-post discovery can be invoked through the CLI. Connection, messaging and engagement functions only create drafts / require the approval layer; they are not bulk-action engines.

### Read commands

```bash
linkedin-agent skills
linkedin-agent status
linkedin-agent read jobs --query "Power BI" --location "Gurgaon"
linkedin-agent read people --query "Power BI recruiter"
linkedin-agent read companies --query "data analytics"
linkedin-agent read posts --query "Power BI"
linkedin-agent read saved
linkedin-agent read profile
```

The first `linkedin-agent login` run should be performed with `HEADLESS=false`. Log in manually in the opened browser and let the local persistent profile retain the session. Playwright documents persistent browser contexts as the mechanism for retaining browser storage locally. citeturn0search0

> **Important:** LinkedIn's current User Agreement prohibits unauthorized automated methods, including bots/scripts that automate activity or scrape/copy services. The repository therefore avoids CAPTCHA bypass, stealth/fingerprint evasion, cookie/session-token extraction and high-volume unsolicited actions. citeturn0search1turn0search3


## Intelligence layer

The project now includes an offline intelligence layer that can work from job records you explicitly provide/export:

- app/intelligence.py — job scoring and filtering
- app/drafting.py — recruiter/follow-up/post drafts
- app/cli_intelligence.py — command-line utilities
- tests/test_intelligence.py — ranking tests

Example commands:

    python -m app.cli_intelligence rank jobs.json
    python -m app.cli_intelligence recruiter-draft "Recruiter" "Power BI Developer" "Power BI, DAX, SQL, Power Query"
    python -m app.cli_intelligence followup-draft "Recruiter" "Power BI Developer"

This layer deliberately separates analysis/drafting from interaction with LinkedIn itself. LinkedIn's current help documentation says third-party software that scrapes or automates activity on LinkedIn is not allowed, and its User Agreement prohibits unauthorized automated methods for scraping, messaging, adding contacts and other engagement. citeturn0search0turn0search1

Accordingly, the project is being developed as a local intelligence + drafting assistant rather than a stealth/unattended LinkedIn bot.
