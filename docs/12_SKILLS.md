# LinkedIn automation skill matrix

The project now has a concrete module for each of the 12 registered skills.

| Skill | Read/draft capability | Direct mutation |
|---|---|---|
| auth | session/login state | No |
| profile | profile snapshot | No |
| jobs | job search/card extraction | No |
| people | people search | No |
| companies | company search | No |
| posts | content search | No |
| saved | saved-post reading | No |
| connections | connection drafts | Approval-gated |
| messaging | message drafts | Approval-gated |
| engagement | engagement drafts | Approval-gated |
| leadgen | lead scoring from collected data | No |
| followups | follow-up records/drafts | Approval-gated |

The browser session is persistent and local. Playwright's persistent context stores session data in the configured user-data directory. Do not copy that directory into Git or share it.

LinkedIn's current User Agreement says unauthorized automated methods and scraping are prohibited. This project therefore keeps mutation behind explicit approval and does not implement CAPTCHA bypass, stealth/fingerprint evasion, credential/session-cookie extraction, or bulk unsolicited engagement.
