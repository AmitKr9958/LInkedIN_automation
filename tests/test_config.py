import os

import pytest
from pydantic_settings import SettingsConfigDict

from app.config import Settings, settings
from app.skills.profile import is_valid_profile_url, require_configured_profile_url


def test_safe_defaults():
    assert settings.dry_run is True
    assert settings.approval_required is True


def test_default_profile_url_is_concrete_slug():
    """Fresh checkout without PROFILE_URL env must still resolve a valid /in/<slug> URL."""

    class IsolatedSettings(Settings):
        model_config = SettingsConfigDict(env_file=None, extra="ignore")

    previous = os.environ.pop("PROFILE_URL", None)
    try:
        isolated = IsolatedSettings()
        assert is_valid_profile_url(isolated.profile_url)
        assert "/in/" in isolated.profile_url
        slug = isolated.profile_url.rstrip("/").split("/in/")[-1]
        assert slug
        assert "amit-kumar-272071153" in isolated.profile_url
    finally:
        if previous is not None:
            os.environ["PROFILE_URL"] = previous


def test_profile_url_env_override_takes_precedence(monkeypatch):
    """PROFILE_URL environment variable must override the config default."""
    monkeypatch.setenv(
        "PROFILE_URL",
        "https://www.linkedin.com/in/env-override-slug/",
    )

    class IsolatedSettings(Settings):
        model_config = SettingsConfigDict(env_file=None, extra="ignore")

    isolated = IsolatedSettings()
    assert isolated.profile_url == "https://www.linkedin.com/in/env-override-slug/"
    assert is_valid_profile_url(isolated.profile_url)


def test_generic_in_url_is_rejected():
    assert not is_valid_profile_url("https://www.linkedin.com/in/")
    assert not is_valid_profile_url("https://www.linkedin.com/in")
    assert not is_valid_profile_url("")
    assert not is_valid_profile_url(None)  # type: ignore[arg-type]


def test_valid_profile_url_accepted():
    assert is_valid_profile_url("https://www.linkedin.com/in/amit-kumar-272071153/")
    assert is_valid_profile_url("https://www.linkedin.com/in/amit-kumar-272071153")
    assert is_valid_profile_url("https://linkedin.com/in/some-slug")


def test_require_configured_profile_url_raises_on_generic():
    with pytest.raises(RuntimeError, match="PROFILE_URL must point to the authenticated"):
        require_configured_profile_url("https://www.linkedin.com/in/")


def test_require_configured_profile_url_returns_valid():
    url = "https://www.linkedin.com/in/amit-kumar-272071153/"
    assert require_configured_profile_url(url) == url


def test_runtime_settings_profile_url_is_usable():
    """The process-global settings singleton must already hold a usable profile URL."""
    assert is_valid_profile_url(settings.profile_url)
    assert require_configured_profile_url(settings.profile_url) == settings.profile_url.strip()
