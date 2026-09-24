import pytest

from app.config import settings
from app.policy import AutomationPolicy, DEFAULT_POLICY, policy_from_settings


def test_safe_defaults():
    assert DEFAULT_POLICY.dry_run is True
    assert DEFAULT_POLICY.require_human_approval is True
    assert DEFAULT_POLICY.allow_scraping is False
    assert DEFAULT_POLICY.allow_security_bypass is False


def test_unsafe_policy_rejected():
    with pytest.raises(ValueError):
        AutomationPolicy(allow_scraping=True).validate()


def test_runtime_policy_matches_settings():
    policy = policy_from_settings()
    assert policy.dry_run == settings.dry_run
    assert policy.require_human_approval == settings.approval_required
