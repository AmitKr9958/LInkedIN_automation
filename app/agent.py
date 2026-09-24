from .action_gateway import ActionGateway, ActionRequest
from .models import JobPreferences


class LinkedInAgent:
    """Orchestrates research, drafting and approval-gated account workflows."""

    def __init__(self, preferences: JobPreferences | None = None, gateway: ActionGateway | None = None):
        self.preferences = preferences or JobPreferences()
        self.gateway = gateway or ActionGateway()

    def system_scope(self) -> dict:
        return {
            "read": [
                "jobs", "profiles", "company pages", "people", "posts",
                "saved items", "own notifications",
            ],
            "draft": [
                "connections", "messages", "comments", "replies",
                "posts", "followups",
            ],
            "analyze": [
                "job ranking", "engager analytics", "thread monitoring",
                "profile optimization", "content planning",
            ],
            "execute": "approval-gated through ActionGateway",
        }

    def request_action(self, action: str, target: str, payload: dict) -> str:
        return self.gateway.request(ActionRequest(action, target, payload))
