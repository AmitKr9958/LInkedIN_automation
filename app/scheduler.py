from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable


@dataclass(frozen=True)
class ScheduledRun:
    name: str
    interval_minutes: int


class ReadOnlyScheduler:
    """Small dependency-free scheduler primitive; callers provide the safe job."""

    def __init__(self, interval_minutes: int = 1440):
        if interval_minutes < 60:
            raise ValueError("minimum scheduler interval is 60 minutes")
        self.interval_minutes = interval_minutes

    def run_once(self, task: Callable[[], object]) -> object:
        return task()

    def metadata(self, name: str = "linkedin-discovery") -> ScheduledRun:
        return ScheduledRun(name, self.interval_minutes)
