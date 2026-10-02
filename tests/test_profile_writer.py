import asyncio

import pytest

from app.profile_writer import ProfileWriteError, apply_approved_profile_proposal


def _proposal():
    return {
        "profile_fingerprint": "missing",
        "profile": {"headline": "Old headline", "about": "Old about"},
        "drafts": {"headline": "New headline", "about": "New about"},
    }


def test_profile_writer_requires_explicit_write_gate(monkeypatch):
    monkeypatch.setattr("app.profile_writer.settings.linkedin_profile_write_enabled", False)
    monkeypatch.setattr("app.profile_writer.settings.dry_run", False)
    with pytest.raises(ProfileWriteError, match="writes are disabled"):
        asyncio.run(apply_approved_profile_proposal(_proposal()))


def test_profile_writer_blocks_dry_run(monkeypatch):
    monkeypatch.setattr("app.profile_writer.settings.linkedin_profile_write_enabled", True)
    monkeypatch.setattr("app.profile_writer.settings.dry_run", True)
    with pytest.raises(ProfileWriteError, match="DRY_RUN"):
        asyncio.run(apply_approved_profile_proposal(_proposal()))
