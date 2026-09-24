# Production Readiness & Pending Issues

## Executive Summary

Current local validation is strong, but the project is **not yet production-ready for the agreed job-discovery workflow**.

### Current verified state

- Git branch: `main`
- Latest user-validated commit before the latest parser changes: `46d47d0`
- Automated tests: **124 passed**
- Skill self-test previously passed with **27 registered skills**
- LinkedIn persistent browser session: **authenticated**
- Live LinkedIn job-search page: **confirmed to load real job results**
- Live probe observed:
  - 25 `li.scaffold-layout__list-item`
  - 25 `[data-occludable-job-id]`
  - 7 `.job-card-container`
  - 7 job links matching `/jobs/view/`
  - visible job results for `Power BI Developer` in Gurgaon
- Application command still returns:
  `[]`

Therefore the principal unresolved defect is **live job-result parsing / runtime integration**. This is not currently an authentication failure, browser-startup failure, or a unit-test failure.

---

## 1. Primary Blocking Issue — Live Job Discovery Returns Empty

### Symptom

This command is still returning an empty list:

```powershell
python -m app read jobs --query "Power BI Developer" --location "Gurgaon"
```

Observed result:

```
[]
```

### What has been proved

The separate live probe demonstrated that LinkedIn is returning job cards in the authenticated session.

The page title was:

```
(29) Power BI Developer Jobs in Gurgaon | LinkedIn
```

The page body contained real job records, including examples such as:

- Power BI Developer — Stackzy Technologies Pvt Ltd — India (Remote)
- Senior Developer, Power BI — Hollister Incorporated — Gurugram, Haryana, India (On-site)
- Senior Power BI Developer — Papigen — India (Remote)
- Power Platform Developer / BI Automation Specialist — Comviva — Gurugram

Therefore the failure is downstream of page loading.

### Most likely code-level causes still requiring verification

1. The parser selects a container but does not consistently extract a valid title/URL/location tuple from the selected node.
2. LinkedIn's current SDUI structure may use nested anchors/containers where the parser's first matching selector produces an incomplete record.
3. The current location extraction can still produce an empty or non-city value, causing the requested-city filter to reject the card.
4. Job-link extraction has been broadened, but a live end-to-end validation is still required after that change.
5. The runtime freshness layer can only keep a result when posting age is known or unknown; we still need to verify that live records actually reach that layer.
6. The current implementation has no structured diagnostic result explaining whether a live card was rejected for URL, title, location, freshness, or deduplication.

### Required engineering work

Implement a **diagnostic parser pipeline** that records per-card extraction state internally:

```
card found
  -> href extracted?
  -> title extracted?
  -> company extracted?
  -> location extracted?
  -> posted extracted?
  -> location accepted?
  -> freshness accepted?
  -> duplicate?
  -> final result
```

This must be logging/diagnostic only and must not collect passwords, cookies, tokens, or session data.

Add deterministic fixtures representing the currently observed LinkedIn SDUI card shapes.

Then validate the live command again.

**Production gate:** `read jobs` must return actual structured job records from the authenticated live page.

---

## 2. Freshness Filtering — Needs Live Verification

The agreed job-search behavior is:

- posted within the last **48 hours**
- stale listings excluded
- unknown posting age handled deliberately

The unit-level freshness filtering exists, but the live path is still blocked by the empty parser result.

### Required

After the live parser is fixed, verify:

- `2 hours ago` is retained
- `1 day ago` is retained
- `2 days ago` is retained/handled according to the exact 48-hour interpretation
- `1 week ago` is excluded
- missing posting age is explicitly classified as unknown rather than silently treated as fresh

**Production gate:** live output must visibly demonstrate freshness behavior.

---

## 3. Location Filtering — Needs Live Verification

The agreed locations are:

- Delhi
- Gurgaon / Gurugram
- Noida
- Jaipur

Remote jobs should only pass when the requested city is explicitly represented, according to the configured policy.

Existing unit coverage verifies important cases such as:

- Gurugram matches Gurgaon
- New Delhi matches Delhi
- Noida does not match Gurgaon
- India (Remote) does not match Gurgaon
- United States (Remote) does not match Delhi
- Gurgaon city + Remote can match Gurgaon

### Remaining work

Verify these filters on the real LinkedIn page after parser repair.

**Production gate:** Gurgaon query must not return US/India-only remote records or unrelated NCR locations.

---

## 4. Job URL / Deduplication Hardening

The code already normalizes job URLs, but the live parser needs verification against:

- `/jobs/view/<id>`
- tracking query parameters
- duplicate cards rendered by SDUI
- selected job/currentJobId state
- repeated cards after scrolling

### Required

Add fixture tests for the currently observed live URL structures and ensure one logical job becomes one record.

---

## 5. Company / Posted-Time Extraction

The current implementation has:

- card selectors
- company selectors
- posted-time selectors
- fallback text extraction
- detail-page hydration
- JSON-LD fallback

This is a good foundation, but it is not yet live-proven on the current page because the top-level parser still returns an empty result.

### Required

Once cards are successfully returned:

- verify company is populated when shown in the card
- verify posted text is populated when shown
- verify detail hydration only occurs when required
- avoid unnecessary navigation that slows discovery

---

## 6. Runtime Contract / Diagnostics

The current CLI returns simply:

```
[]
```

That makes debugging difficult.

### Required

Provide a safe debug mode such as:

```powershell
python -m app read jobs --query "Power BI Developer" --location "Gurgaon" --debug
```

or equivalent logging configuration.

The diagnostic output should report counts, for example:

- cards detected
- URLs extracted
- titles extracted
- locations extracted
- records rejected by location
- records rejected as stale
- duplicates removed
- final records

It should never print:

- passwords
- OTPs
- cookies
- session tokens
- authentication headers

---

## 7. Browser Smoke Test

Unit tests currently pass, but a real authenticated LinkedIn session is intentionally not used in CI.

### Required production validation

Run the existing local authenticated smoke workflow after the parser is repaired:

1. authenticated session check
2. jobs page
3. people page
4. companies page
5. posts page
6. saved page
7. profile page

This must be run locally because CI cannot use the real LinkedIn session.

---

## 8. Documentation Accuracy

The current documentation contains a few stale claims/inconsistencies that should be corrected before release.

Examples:

- README/docs contain references to **26 skills**, while the current self-test reports **27 skills**.
- Some status text says live job parsing and 48-hour filtering were verified, but the latest user validation still returns `[]`.
- There are duplicated entries in the production-readiness skill lists.
- Some release-readiness statements are stronger than the current live evidence supports.

### Required

Update README and production-readiness documentation only after the live job command succeeds.

Documentation must distinguish:

- unit-tested
- locally browser-tested
- live-account verified
- not yet verified

---

## 9. Production Features Previously Agreed

After the blocking live job-parser issue is resolved, the previously agreed production scope is:

### Job discovery

- Power BI / BI / Data Analyst searches
- Delhi / Gurgaon / Noida / Jaipur
- 48-hour freshness
- remote handling
- duplicate removal
- preference-based ranking
- Easy Apply preference
- internship/fresher exclusion
- local job history

### Recruiter / HR / Hiring Manager workflow

- identify relevant people
- classify recruiter / HR / hiring manager
- score relevance
- generate connection drafts
- generate follow-up drafts
- link outreach to the relevant job
- keep consequential actions approval-gated

### Content system

- Post Audit
- Story Bank
- central Voice Engine
- humanization / cleanup
- hook extraction/planning
- repurposing
- optional media prompt generation
- controlled publishing workflow

### Application tracking

- shortlist
- applied
- interview
- offer
- rejected / closed states
- notes
- JSON/CSV export

### Safety / operational controls

- DRY_RUN by default
- human approval for consequential actions
- no password/OTP/token export
- no CAPTCHA bypass
- no stealth/fingerprint evasion
- no uncontrolled bulk messaging
- no real LinkedIn credentials in CI
- persistent local browser profile

---

## 10. Production Release Gates

The project should not be declared production-ready until all of the following are true:

### Automated gates

- `python -m compileall -q app tests`
- `ruff check app tests --select E9,F63,F7,F82`
- `pytest -q -m "not e2e"`
- self-test passes
- policy tests pass
- action-gateway tests pass
- application tracker tests pass
- Story Bank/outreach/content contract tests pass
- no secrets/browser profile committed

### Live local gates

- authenticated session detected
- `read profile` succeeds
- `read jobs` returns actual jobs
- 48-hour freshness verified
- location filtering verified
- recruiter/HR/hiring-manager discovery verified
- content audit verified
- approval queue verified
- application tracking verified
- export verified

### Documentation gates

- skill counts consistent
- production status accurately reflects evidence
- setup instructions current
- known limitations documented

---

## 11. Current Status Summary

| Area | Status |
|---|---|
| Python/unit test suite | PASS — 124 tests |
| Skill self-test | PASS — 27 skills |
| LinkedIn authentication | PASS |
| LinkedIn live job page | PASS |
| Live job cards visible | PASS |
| Job parser end-to-end | **BLOCKED — returns []** |
| 48-hour freshness live verification | **PENDING** |
| City filtering live verification | **PENDING** |
| Job ranking live verification | **PENDING** |
| Recruiter/HR/HM workflow | Implemented locally; live verification pending |
| Content/Story Bank/Voice | Implemented + tested |
| Application tracker | Implemented + tested |
| Approval/safety controls | Implemented + tested |
| Production release | **NOT READY YET** |

---

## 12. Recommended Order of Work

### Phase 1 — Blocking
Fix and instrument the live job parser until:

```python
python -m app read jobs --query "Power BI Developer" --location "Gurgaon"
```

returns structured records.

### Phase 2 — Job-quality validation
Verify:

- location
- 48-hour freshness
- deduplication
- company
- posted time
- Easy Apply
- ranking

### Phase 3 — Full live smoke validation
Verify profile, people, companies, posts, saved, jobs.

### Phase 4 — Documentation/release hardening
Correct stale skill counts and release claims.

### Phase 5 — Production packaging
Add the read-only scheduled discovery workflow and optional local dashboard/browser handoff described in the roadmap.

---

## User-side Requirement

At this moment, **no new credential, login, or configuration is required from the user**.

The only remaining user-side action is to run the next validation command after a parser fix is committed and pull the latest `main`.

Do not provide or store passwords, OTPs, cookies, or LinkedIn session tokens.
