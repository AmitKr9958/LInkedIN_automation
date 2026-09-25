# Reference capability parity matrix

Reference: sergebulaev/linkedin-skills (conceptual feature set).
Source of truth for skill count: local registry (27 skills).

| Reference capability | Current implementation | Unit tests | Live validation | Status |
|---------------------|------------------------|------------|-----------------|--------|
| Post Writer | `post_writer` via content_skills + dispatch | yes | pending | present |
| Comment Drafter | `comment_drafter` | yes | pending | present |
| Reply Handler | `reply_handler` | yes | pending | present |
| Post Audit | `post_audit` | yes | pending | present |
| Humanizer | `humanizer` (no detector-evasion claims) | yes | pending | present |
| Hook Extractor | `hook_extractor` | yes | pending | present |
| Content Planner | `content_planner` | yes | pending | present |
| Engagement Monitor | `engager_analytics` + `thread_monitor` | yes | pending | present |
| Profile Optimizer | `profile_optimizer` | yes | pending | present |
| Employee Advocacy | `employee_advocacy` | yes | pending | present |
| Repurposer | `repurposer` | yes | pending | present |
| Interviewer | `interviewer` | yes | pending | present |
| Story Bank | `story_bank` + persistence | yes | pending | present |
| Media prompt workflow | `media` module | yes | n/a | present |
| Publishing workflow | `publishing` + approval | yes | n/a | present |
| Job search / parser | `jobs` skill + detail hydration | yes | live-validated (parser) | present |
| 48h freshness default | preferences → CLI → runtime | yes | needs re-verify after fix | fixed |
| Location filter | Gurugram/Delhi/Noida/Jaipur aliases | yes | live-validated | present |
| Recruiter/HR outreach | `outreach` + approval queue | yes | n/a (gated) | present |
| Follow-up scheduling | `followups` lifecycle | yes | n/a (gated) | present |
| Application tracking | `application_tracker` statuses | yes | n/a | present |
| Approval queue | `approval_queue` | yes | n/a | present |
| Job history | `history` | yes | n/a | present |
| Reporting/export | `reporting` JSON/CSV | yes | n/a | present |

Notes:
- Live validation requires the authenticated local browser profile on the user's machine.
- Mutating skills remain DRY_RUN + APPROVAL_REQUIRED by default.
- Parity is feature-level, not a line-by-line code copy of the reference repository.
