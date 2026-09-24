from .models import JobPreferences

class LinkedInAgent:
    """Orchestrates read-only research and approved account actions."""

    def __init__(self, preferences: JobPreferences | None = None):
        self.preferences = preferences or JobPreferences()

    def system_scope(self) -> dict:
        return {
            "read": ["jobs", "profiles", "company pages", "own notifications"],
            "draft": ["connections", "messages", "comments", "posts"],
            "execute": ["only after explicit approval"],
        }
