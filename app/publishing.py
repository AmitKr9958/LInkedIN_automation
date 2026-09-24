from __future__ import annotations

from dataclasses import dataclass

from .agent import LinkedInAgent


@dataclass(frozen=True)
class PublishRequest:
    text: str
    media_urls: tuple[str, ...] = ()
    scheduled_for: str = ""

    def payload(self) -> dict:
        return {
            "text": self.text,
            "media_urls": list(self.media_urls),
            "scheduled_for": self.scheduled_for,
        }


def queue_publish(request: PublishRequest, agent: LinkedInAgent | None = None) -> str:
    """Queue an explicitly approved publishing intent; no direct LinkedIn posting."""
    return (agent or LinkedInAgent()).request_action(
        "publish_post",
        "linkedin",
        request.payload(),
    )
