from __future__ import annotations

from dataclasses import dataclass

from .config import settings


@dataclass(frozen=True)
class AutomationPolicy:
    """Non-negotiable safety and reliability constraints."""

    dry_run: bool = True
    require_human_approval: bool = True
    max_actions_per_run: int = 5
    max_payload_bytes: int = 64 * 1024
    allowed_actions: frozenset[str] = frozenset({
        "connection_request",
        "message",
        "followup_message",
        "comment",
        "reply",
        "like",
        "publish_post",
        "job_application",
    })
    allow_unsolicited_bulk_messaging: bool = False
    allow_scraping: bool = False
    allow_security_bypass: bool = False
    allow_credential_export: bool = False

    def validate(self) -> None:
        if self.max_actions_per_run < 1:
            raise ValueError("max_actions_per_run must be >= 1")
        if self.max_payload_bytes < 1024:
            raise ValueError("max_payload_bytes must be >= 1024")
        if not self.allowed_actions:
            raise ValueError("allowed_actions must not be empty")
        if self.allow_unsolicited_bulk_messaging:
            raise ValueError("Bulk unsolicited messaging is disabled by policy")
        if self.allow_scraping:
            raise ValueError("Scraping is disabled by policy")
        if self.allow_security_bypass:
            raise ValueError("Security/access-control bypass is disabled by policy")
        if self.allow_credential_export:
            raise ValueError("Credential/session export is disabled by policy")


def policy_from_settings() -> AutomationPolicy:
    """Build the runtime policy from the same settings used by the CLI."""
    policy = AutomationPolicy(
        dry_run=settings.dry_run,
        require_human_approval=settings.approval_required,
    )
    policy.validate()
    return policy


DEFAULT_POLICY = AutomationPolicy()
DEFAULT_POLICY.validate()
