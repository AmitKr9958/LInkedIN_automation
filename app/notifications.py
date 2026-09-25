from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import smtplib
from email.message import EmailMessage


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


class EmailNotificationProvider(NotificationProvider):
    """SMTP provider; credentials come only from environment variables."""

    def __init__(self, host: str | None = None, port: int = 587, username: str | None = None,
                 password: str | None = None, sender: str | None = None, recipient: str | None = None):
        self.host = host or os.getenv("SMTP_HOST", "")
        self.port = int(os.getenv("SMTP_PORT", str(port)))
        self.username = username or os.getenv("SMTP_USERNAME", "")
        self.password = password or os.getenv("SMTP_PASSWORD", "")
        self.sender = sender or os.getenv("NOTIFICATION_FROM", self.username)
        self.recipient = recipient or os.getenv("NOTIFICATION_TO", "")

    def send(self, notification: Notification) -> None:
        if not all((self.host, self.sender, self.recipient)):
            raise RuntimeError("SMTP notification configuration is incomplete")
        message = EmailMessage()
        message["Subject"] = notification.subject
        message["From"] = self.sender
        message["To"] = self.recipient
        message.set_content(notification.body)
        with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
            smtp.starttls()
            if self.username:
                smtp.login(self.username, self.password)
            smtp.send_message(message)
