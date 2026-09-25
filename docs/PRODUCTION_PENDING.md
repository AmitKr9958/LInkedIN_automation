# LinkedIn Automation Agent — Current Issues & Pending Work

## 1. Current Status

The project is **not production-ready yet**.

The automated codebase is currently healthy:

- **124 automated tests pass**
- **27 skills are registered and self-test successfully**
- LinkedIn authentication through the persistent local browser profile works
- The live LinkedIn job-search page loads successfully
- The live LinkedIn page contains real job cards

However, the application-level job discovery command still returns an empty result:

```powershell
python -m app read jobs --query "Power BI Developer" --location "Gurgaon"
```

Current result:

```
[]
```

This is the primary blocking issue.

---

# 2. PRIMARY BLOCKER — LIVE JOB PARSER

## Problem

LinkedIn is returning job results in the authenticated browser, but the application's `jobs.search()` pipeline is not returning those jobs to the CLI.

The live probe demonstrated:

- LinkedIn job-search page loaded
- Correct Gurgaon search page
- 25 `[data-occludable-job-id]` elements
- 7 `.job-card-container` elements
- 7 job links containing `/jobs/view/`
- Visible job listings in the page body

Therefore:

**Browser/session = working**

**LinkedIn search page = working**

**Automated tests = working**

**Application job extraction/filtering = still failing**

---

# 3. What Must Be Resolved

The job parser needs to be traced end-to-end and made observable.

For every detected card, the parser must verify:

```
Job card detected
      ↓
Job URL extracted
      ↓
Job title extracted
      ↓
Company extracted
      ↓
Location extracted
      ↓
Posted time extracted
      ↓
Location filter applied
      ↓
48-hour freshness filter applied
      ↓
Duplicate check applied
      ↓
Job returned
```

At present, we do not have enough diagnostic information to identify exactly which stage is causing the live records to disappear.

## Required fix

Add safe diagnostic logging/counts showing:

- number of cards detected
- number of URLs extracted
- number of titles extracted
- number of companies extracted
- number of locations extracted
- number rejected because location did not match
- number rejected because freshness exceeded 48 hours
- number rejected as duplicates
- final number returned

The diagnostic output must never expose passwords, OTPs, cookies, session tokens, or authentication headers.

---

# 4. LIVE SDUI SELECTOR VALIDATION

LinkedIn is currently using an SDUI-style job-result structure.

The live page showed selectors such as:

```
[data-occludable-job-id]
.job-card-container
li:has(a[href*="/jobs/view/"])
[data-job-id]
```

The parser has already been updated to prioritize these structures.

It has also been updated to broaden job-link extraction.

## Still pending

The updated parser must be tested against the real authenticated page and must return actual `Job` objects.

If extraction still fails, capture only safe structural diagnostics and update the parser based on the actual live DOM.

---

# 5. LOCATION FILTERING

Required supported locations:

- Delhi
- Gurgaon / Gurugram
- Noida
- Jaipur

Expected behavior:

- Gurugram should match Gurgaon
- New Delhi should match Delhi
- Noida should not match Gurgaon
- India-only Remote should not be treated as Gurgaon
- US Remote should not be treated as Delhi
- A job explicitly saying Gurgaon + Remote may match Gurgaon

## Status

Unit tests exist and pass.

## Pending

Live validation is still required because the live parser currently returns no jobs.

---

# 6. 48-HOUR FRESHNESS

Required job-search rule:

**Only jobs posted within the configured 48-hour window should be returned for the job-discovery workflow.**

Examples that need verification:

- 2 hours ago → included
- 12 hours ago → included
- 1 day ago → included
- older than 48 hours → excluded
- unknown posting age → handled explicitly and consistently

## Status

The freshness filter exists and has unit coverage.

## Pending

Live end-to-end validation is blocked by the empty parser result.

---

# 7. JOB DATA QUALITY

Each returned job should contain, where LinkedIn exposes the information:

- title
- company
- location
- URL
- posted text
- posted age in hours
- Easy Apply indicator
- source
- relevant visible text/description

## Pending

Verify these fields against real live results after the parser begins returning jobs.

---

# 8. DEDUPLICATION

The system must ensure the same LinkedIn job is returned only once.

It should handle:

- repeated SDUI cards
- tracking parameters
- current selected job state
- duplicate URLs
- repeated cards after scrolling

## Pending

Add live fixture/regression coverage based on the current LinkedIn result structure and verify actual discovery output.

---

# 9. JOB RANKING / PREFERENCES

The agreed job preferences include:

- Power BI Developer
- Power BI
- Business Intelligence
- Data Analyst
- BI Developer
- Reporting Analyst

Preferred locations:

- Delhi
- Gurgaon
- Noida
- Jaipur

Other preferences:

- recent postings
- approximately 5–12 years experience range
- Easy Apply preferred
- internships excluded
- fresher roles excluded
- remote only when explicitly permitted by the location policy

## Pending

Ranking cannot be properly validated until live jobs are successfully returned.

---

# 10. RECRUITER / HR / HIRING MANAGER WORKFLOW

The planned workflow includes:

1. Discover relevant jobs.
2. Identify recruiter / HR / hiring-manager targets.
3. Classify the target.
4. Score relevance.
5. Draft a job-specific connection message.
6. Draft follow-up messages.
7. Link outreach to the relevant job.
8. Keep consequential actions behind human approval.

## Status

Local implementation and tests exist.

## Pending

End-to-end live validation should occur after job discovery is fixed.

---

# 11. CONTENT SYSTEM

The agreed content features include:

- Post Audit
- Story Bank
- Central Voice Engine
- Humanization
- Hook extraction/planning
- Repurposing
- Optional media prompt generation
- Controlled publishing workflow

## Status

These components have been implemented and covered by automated tests.

## Pending

Final production validation and documentation consistency.

---

# 12. APPLICATION TRACKING

Required workflow:

- shortlist
- applied
- interview
- offer
- rejected / closed
- notes
- JSON/CSV export

## Status

Implemented locally and tested.

## Pending

Final end-to-end workflow validation.

---

# 13. SAFETY / SECURITY REQUIREMENTS

These remain mandatory for production:

- DRY_RUN enabled by default
- consequential actions require human approval
- no password storage by the agent
- no OTP handling by the agent
- no cookie/session-token export
- no CAPTCHA bypass
- no security/access-control bypass
- no stealth/fingerprint evasion
- no uncontrolled bulk messaging
- no real authenticated LinkedIn session in CI
- persistent browser profile remains local and private

These boundaries should remain unchanged.

---

# 14. TESTING REQUIRED BEFORE PRODUCTION

## Automated

All of the following must pass:

```powershell
python -m compileall -q app tests
ruff check app tests --select E9,F63,F7,F82
pytest -q -m "not e2e"
python -m app selftest
```

Current known automated result:

```
124 passed
27 skills self-test PASS
```

## Live local validation

Must pass:

```powershell
python -m app debug-auth
python -m app read profile
python -m app read jobs --query "Power BI Developer" --location "Gurgaon"
```

The third command is currently the blocker.

---

# 15. DOCUMENTATION CLEANUP

Before release:

- Ensure README skill count matches the actual registry.
- Remove duplicated skill entries.
- Remove outdated statements claiming live job parsing is verified.
- Clearly distinguish:
  - unit tested
  - browser tested
  - live-account verified
  - pending
- Keep production status accurate.

---

# 16. PRODUCTION RELEASE ORDER

The work should be completed in this order:

### Phase 1 — Fix the blocking parser

Make:

```
python -m app read jobs --query "Power BI Developer" --location "Gurgaon"
```

return actual structured jobs.

### Phase 2 — Validate job quality

Verify:

- title
- company
- location
- URL
- posted time
- 48-hour freshness
- Easy Apply
- deduplication

### Phase 3 — Validate preferences and ranking

Verify:

- target locations
- experience
- internship/fresher exclusions
- remote rules
- ranking

### Phase 4 — Live smoke test

Validate:

- authentication
- profile
- jobs
- people
- companies
- posts
- saved items

### Phase 5 — Validate workflows

Validate:

- recruiter/HR/hiring-manager workflow
- outreach drafting
- follow-ups
- application tracking
- approval queue
- reporting/export

### Phase 6 — Documentation and release hardening

Update:

- README
- production-readiness documentation
- skill counts
- known limitations
- setup instructions

### Phase 7 — Production release

Only after the above gates pass should the project be considered production-ready.

---

# 17. CURRENT PENDING CHECKLIST

| Item | Status |
|---|---|
| Python environment | PASS |
| Automated tests | PASS — 124 |
| Skill registry/self-test | PASS — 27 |
| LinkedIn authentication | PASS |
| Live LinkedIn job page | PASS |
| Live job cards detected | PASS |
| Application job parser | **BLOCKED** |
| Job CLI returns results | **PENDING** |
| 48-hour live validation | PENDING |
| Location live validation | PENDING |
| Job deduplication live validation | PENDING |
| Job ranking live validation | PENDING |
| Recruiter/HR/HM live workflow | PENDING |
| Full live smoke test | PENDING |
| Documentation cleanup | PENDING |
| Production release | **NOT READY** |

---

# 18. USER-SIDE REQUIREMENT

At this stage, **nothing additional is required from the user's side** except running the validation commands after a new parser fix is committed.

No password, OTP, cookie, `li_at` token, or other session credential should be provided.

The primary engineering responsibility remaining is to fix and verify the live job parser.

## Definition of Done

The primary blocker is considered resolved only when:

```powershell
python -m app read jobs --query "Power BI Developer" --location "Gurgaon"
```

returns real structured jobs from the authenticated LinkedIn page, and those jobs correctly pass the agreed location, freshness, deduplication, and preference rules.

Only then should the project move to the remaining production-release gates.

## Recent fix (working tree)

- Default 48-hour freshness is now applied automatically for `python -m app read jobs`
  from centralized `UserJobPreferences.posted_within_hours` (no need to pass
  `--max-posted-hours 48` every time). Pass a negative value to disable the filter.
- Unknown posting age (`posted_hours is None`) is **excluded** under the strict
  48-hour policy (no longer treated as fresh). Diagnostics report `unknown_posted_age`.
- Incomplete Job records (missing title or href) are rejected after detail hydration.
  Detail pages are visited when title/company/posted/location is missing so titles
  can be recovered.
- Read-only smoke test: `python -m app smoke-test --read-only`

