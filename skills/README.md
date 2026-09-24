# LinkedIn Skill Registry

The project uses modular LinkedIn skills. Each skill separates read/draft/execute behavior and can be composed by the orchestrator.

## Skill map

1. auth — session and login state
2. profile — profile/skills/audit data
3. jobs — job search and job details
4. people — people/recruiter research
5. companies — company research
6. posts — post data and content workflows
7. saved — saved-post workflows
8. connections — connection drafts and controlled requests
9. messaging — message drafts and controlled sends
10. engagement — comments/replies/likes with approval
11. leadgen — prospect lists and outreach plans
12. followups — follow-up queue and scheduling

The read-oriented skills are designed to be safe to run in dry-run mode. Account-changing execution is routed through the central approval gate.
