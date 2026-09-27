"""Exclusive file lock so only one agent cycle runs at a time.

Uses an atomic exclusive create on a lock file under data/. Safe on local
Windows and Linux filesystems. Stale locks older than STALE_SECONDS are
reclaimed so a crashed process does not block forever.
"""
from __future__ import annotations

import atexit
import os
import time
from contextlib import contextmanager
from pathlib import Path

from .config import ROOT

LOCK_PATH = ROOT / "data" / "agent.lock"
STALE_SECONDS = 50 * 60  # 50 minutes — exceeds scheduler ExecutionTimeLimit (45m) + buffer


class AgentAlreadyRunning(RuntimeError):
    """Raised when another agent process holds the lock."""


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False
    except Exception:
        return False


def _is_stale(path: Path) -> bool:
    try:
        age = time.time() - path.stat().st_mtime
        if age < STALE_SECONDS:
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
            if text.isdigit() and _pid_alive(int(text)):
                return False
            return not (text.isdigit() and _pid_alive(int(text)))
        return True
    except OSError:
        return True


@contextmanager
def agent_lock(path: Path | None = None):
    """Acquire an exclusive agent lock or raise AgentAlreadyRunning."""
    lock_path = path or LOCK_PATH
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if lock_path.exists() and not _is_stale(lock_path):
        raise AgentAlreadyRunning(
            f"Another agent cycle is already running (lock: {lock_path}). "
            "Wait for it to finish or remove a stale lock after confirming "
            "no agent process is active."
        )

    if lock_path.exists():
        try:
            lock_path.unlink()
        except OSError:
            pass

    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(lock_path), flags)
    except FileExistsError as exc:
        raise AgentAlreadyRunning(
            f"Another agent cycle is already running (lock: {lock_path})."
        ) from exc

    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.close(fd)
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        try:
            lock_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise

    def _cleanup() -> None:
        try:
            if lock_path.exists():
                text = lock_path.read_text(encoding="utf-8", errors="ignore").strip()
                if text == str(os.getpid()):
                    lock_path.unlink(missing_ok=True)
        except Exception:
            pass

    atexit.register(_cleanup)
    try:
        yield lock_path
    finally:
        atexit.unregister(_cleanup)
        _cleanup()
