from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from .approval_queue import ApprovalItem


class OutreachValidationError(ValueError):
    """Raised when an approved outreach item is not safe for manual handling."""


@dataclass(frozen=True)
class OutreachPacket:
    review_id: str
    target: str
    message: str


def validate_manual_outreach(item: ApprovalItem) -> OutreachPacket:
    """Validate an approved message for the human-send workflow.

    This deliberately does not open LinkedIn, click Message, or send anything.
    LinkedIn currently prohibits third-party automation of message sending.
    """
    if item.action not in {"message", "connection_request"}:
        raise OutreachValidationError("Only approved message or connection-request items can enter the outreach workspace.")
    if item.status != "approved":
        raise OutreachValidationError("Only approved outreach items can enter the outreach workspace.")

    target = item.target.strip()
    parsed = urlparse(target)
    if parsed.scheme != "https" or parsed.netloc.lower() not in {"linkedin.com", "www.linkedin.com"}:
        raise OutreachValidationError("Outreach target must be an https://www.linkedin.com profile URL.")
    if not parsed.path.rstrip("/").lower().startswith("/in/"):
        raise OutreachValidationError("Outreach target must be a LinkedIn /in/ profile URL.")

    message = " ".join(item.payload.split()).strip()
    if not message:
        raise OutreachValidationError("Approved outreach message is empty.")
    if len(message) > 1900:
        raise OutreachValidationError("Approved outreach message exceeds the safe manual-review limit of 1900 characters.")

    return OutreachPacket(review_id=item.id, target=target, message=message)


def manual_sent_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
