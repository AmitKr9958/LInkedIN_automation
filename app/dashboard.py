from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .config import ROOT
from .run_status import read_run_status
from .skill_center import skill_catalog, run_skill
from .store import list_activity
from .application_tracker import ApplicationTracker, STATUSES, TRANSITIONS
from .job_preferences import DEFAULT_JOB_PREFERENCES
from .run_lock import AgentAlreadyRunning, agent_lock
from .platform.agent_runner import AgentRunError, AgentRunner


# One worker prevents two Playwright sessions from competing for the same
# persistent LinkedIn profile. The HTTP server itself remains responsive.
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="linkedin-dashboard")
_TASKS: dict[str, dict] = {}
_TASK_LOCK = threading.Lock()
_MAX_TASKS = 100
_MAX_REQUEST_BODY_BYTES = 1_048_576


def _run_agent_with_lock():
    """Compatibility adapter: dashboard execution uses the V3 runner boundary."""
    try:
        return AgentRunner().run(max_posted_hours=6)
    except AgentRunError as exc:
        if isinstance(exc.__cause__, AgentAlreadyRunning) or exc.result.state.value == "blocked":
            raise AgentAlreadyRunning(str(exc)) from exc
        raise

