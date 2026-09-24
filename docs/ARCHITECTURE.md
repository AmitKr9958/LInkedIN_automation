# Architecture

The project is intentionally split into five layers:

1. **Browser** — Playwright persistent context using a local browser profile.
2. **Workflows** — LinkedIn-specific page navigation and extraction.
3. **Agent** — reasoning, ranking and drafting.
4. **Approval** — explicit gate for consequential actions.
5. **Store** — local activity/audit database.

The first implementation should prioritize reliable read operations and dry-run previews. UI selectors will be isolated in workflow modules so LinkedIn UI changes do not require rewriting the orchestration layer.
