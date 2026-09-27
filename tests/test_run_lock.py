from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.run_lock import AgentAlreadyRunning, agent_lock


def test_agent_lock_exclusive(tmp_path: Path):
    lock = tmp_path / "agent.lock"
    with agent_lock(lock):
        assert lock.exists()
        assert lock.read_text().strip() == str(os.getpid())
        with pytest.raises(AgentAlreadyRunning):
            with agent_lock(lock):
                pass
    assert not lock.exists()


def test_stale_lock_reclaimed(tmp_path: Path, monkeypatch):
    lock = tmp_path / "agent.lock"
    lock.write_text("999999999", encoding="utf-8")
    import app.run_lock as rl
    monkeypatch.setattr(rl, "STALE_SECONDS", 0)
    with agent_lock(lock):
        assert lock.read_text().strip() == str(os.getpid())
    assert not lock.exists()
