# Production Pending

Updated for the production-hardening work on the `production-hardening` branch.

## Implemented hardening
- Bounded incremental scrolling and capture for virtualized LinkedIn job results.
- Stable URL deduplication across scroll steps.
- Final DOM parsing remains as a second-pass enrichment layer.
- Applicant-count and experience metadata extraction.
- Read-only scheduling/notifications, resume matching/tailoring and application lifecycle tracking.
- CI security checks for dependency vulnerabilities and secret scanning.

## Remaining production gates
1. Run the complete local automated suite on the hardened branch.
2. Verify GitHub Actions unit, browser-smoke, dependency-audit and secret-scan results.
3. Validate authenticated live read-only job searches for Delhi, Gurgaon/Gurugram, Noida and Jaipur, including remote/hybrid/on-site cases.
4. Validate incremental virtualized capture against the user's current LinkedIn UI and compare unique-card counts with the rendered result set.
5. Validate profile, people, companies, posts and saved reads after current LinkedIn SDUI changes.
6. Validate scheduled read-only discovery and notification/report delivery.
7. Review all remaining parser/selector regressions after LinkedIn UI changes.
8. Keep publishing, messaging, connections, engagement and followups approval-gated and audited.

## Safety constraints
No CAPTCHA/MFA bypass, stealth/fingerprint evasion, cookie/session-token export, password storage, uncontrolled bulk messaging or uncontrolled engagement. Mutating actions remain human-approved and auditable.

## Production status
**Implementation is hardened but not declared production-ready until automated CI and applicable authenticated live read-only validation are demonstrated.**
