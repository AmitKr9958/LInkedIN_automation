from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AutomationPolicy:
    """Non-negotiable safety and reliability constraints."""

    dry_run: bool = True
    require_human_approval: bool = True
    max_actions_per_run: int = 5
    allow_unsolicited_bulk_messaging: bool = False
    allow_scraping: bool = False
    allow_security_bypass: bool = False
    allow_credential_export: bool = False

    def validate(self) -> None:
        if self.max_actions_per_run < 1:
            raise ValueError("max_actions_per_run must be >= 1")
        if self.allow_unsolicited_bulk_messaging:
            raise ValueError("Bulk unsolicited messaging is disabled by policy")
        if self.allow_scraping:
            raise ValueError("Scraping is disabled by policy")
        if self.allow_security_bypass:
            raise ValueError("Security/access-control bypass is disabled by policy")
        if self.allow_credential_export:
            raise ValueError("Credential/session export is disabled by policy")


DEFAULT_POLICY = AutomationPolicy()
