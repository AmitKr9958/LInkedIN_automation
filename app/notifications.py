from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json


@dataclass(frozen=True)
class Notification:
    subject: str
    body: str


class NotificationProvider:
    def send(self, notification: Notification) -> None:
        raise NotImplementedError


class ConsoleNotificationProvider(NotificationProvider):
    def send(self, notification: Notification) -> None:
        print(f"[{notification.subject}]")
        print(notification.body)


class FileNotificationProvider(NotificationProvider):
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def send(self, notification: Notification) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"subject": notification.subject, "body": notification.body}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def build_daily_report(jobs: list[dict], pending_approvals: int = 0, followups_due: int = 0) -> Notification:
    lines = [f"New matching jobs: {len(jobs)}", f"Pending approvals: {pending_approvals}", f"Follow-ups due: {followups_due}"]
    for job in jobs:
        lines.append(
            " | ".join(
                str(job.get(key) or "")
                for key in ("title", "company", "location", "posted", "applicant_count", "application_url")
            )
        )
    return Notification("LinkedIn career agent daily report", "\n".join(lines))
