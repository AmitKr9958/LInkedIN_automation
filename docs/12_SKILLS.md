# LinkedIn automation skill matrix

The project registers **24 governed skills**: the original 12 capability skills plus 12 local content/intelligence skills. `python -m app skills` prints the authoritative list from `app/skill_registry.py`.

## Core capability skills (12)

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

## Content/intelligence skills (12, fully local)

| Skill | Capability |
|---|---|
| post_writer | Draft original posts from a topic and angle |
| content_planner | Build multi-day content plans |
| comment_drafter | Draft comments for supplied posts |
| reply_handler | Draft replies to comments and threads |
| humanizer | Mechanical writing cleanup; no detector-evasion claim |
| hook_extractor | Analyze the structure of a supplied hook |
| repurposer | Adapt supplied source content into LinkedIn-native copy |
| profile_optimizer | Audit profile sections; identify missing information |
| interviewer | Generate concrete story-building interview questions |
| engager_analytics | Analyze supplied engager records |
| thread_monitor | Identify recent author replies needing follow-up |
| employee_advocacy | Create a governed employee advocacy plan |

The browser session is persistent and local. Playwright's persistent context stores session data in the configured user-data directory. Do not copy that directory into Git or share it.

LinkedIn's current User Agreement says unauthorized automated methods and scraping are prohibited. This project therefore keeps mutation behind explicit approval and does not implement CAPTCHA bypass, stealth/fingerprint evasion, credential/session-cookie extraction, or bulk unsolicited engagement.
