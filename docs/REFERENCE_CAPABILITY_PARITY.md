# Reference Capability Parity

This document describes capability parity at the architectural level, not unrestricted LinkedIn account automation.

| Capability | Status | Evidence / limitation |
|---|---|---|
| Job discovery | Implemented | Live SDUI parser and detail hydration |
| Freshness | Implemented | 48-hour default with strict unknown-age policy |
| Location filtering | Implemented | Gurgaon/Gurugram aliases and configured locations |
| Applicant count | Implemented in parser | Requires live UI coverage validation |
| Experience matching | Implemented | Configurable range and role hints |
| Job ranking | Implemented | Explainable reasons |
| Recruiter/HR/HM outreach planning | Implemented | Draft/approval workflow; live E2E pending |
| Follow-ups | Implemented | Persistent lifecycle |
| Application tracking | Implemented | Persistent lifecycle and audit events |
| Resume matching | Implemented | Uses supplied facts only |
| Resume tailoring | Implemented | Suggestions only; no invented facts |
| Content engine | Implemented | Existing skills preserved |
| Media | Partial | Prompt layer; provider abstraction remains limited |
| Publishing | Approval intent only | No unrestricted direct publisher |
| Scheduling | Implemented | Safe read-only scheduler primitive/CLI |
| Notifications | Implemented | Console/file/SMTP provider |
| Security controls | Implemented | No credential export, bypass or stealth |
| Live 27-skill validation | Pending | Requires local authenticated read-only run |
| CI final release evidence | Pending | Must be verified from actual GitHub workflow run |

## Safety boundary

The project intentionally does not implement CAPTCHA/MFA bypass, stealth/fingerprint evasion, session-cookie extraction, password storage, uncontrolled bulk messaging or uncontrolled engagement.
