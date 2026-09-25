# Production Pending

Updated for the production-hardening work on commit lineage starting at 0126d54.

## Verified baseline
- 27 skills registered.
- 156 tests were previously passing locally at 0126d54.
- Authenticated local LinkedIn session works.
- Live SDUI job parsing works.
- Gurgaon filtering and 48-hour freshness work.
- Profile, people, companies, posts and saved reads work.

## Remaining production gates
1. Applicant-count extraction and configurable preference signals.
2. Experience parsing/matching across range, plus/minimum and senior/lead/manager forms.
3. Live validation matrix for Delhi, Gurgaon/Gurugram, Noida and Jaipur plus remote/hybrid/on-site cases.
4. External application URL extraction where LinkedIn exposes a safe external link.
5. End-to-end recruiter/HR/hiring-manager workflow validation.
6. Application lifecycle integration and duplicate prevention.
7. Resume/job matching and factual resume tailoring.
8. Optional media provider abstraction with CI mock provider.
9. Approval-gated publishing integration; no unrestricted automation.
10. Scheduled read-only discovery and notification/report delivery.
11. Full 27-skill contract validation and safety coverage.
12. GitHub Actions verification on the hardened branch/main.
13. Security and secret-scan verification.
14. Documentation synchronization.

## Safety constraints
No CAPTCHA/MFA bypass, stealth/fingerprint evasion, cookie/session-token export, password storage, uncontrolled bulk messaging or uncontrolled engagement. Mutating actions remain human-approved and auditable.

## Production status
**Not production-ready until the release gates are demonstrated with automated results and applicable live read-only validation.**
