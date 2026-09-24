from datetime import datetime, timezone
from pydantic import BaseModel, Field

class JobPreferences(BaseModel):
    keywords: list[str] = Field(default_factory=lambda: ["Power BI", "Business Intelligence", "Data Analyst"])
    locations: list[str] = Field(default_factory=lambda: ["Delhi", "Gurgaon", "Noida", "Jaipur"])
    posted_within_hours: int = 48
    easy_apply_only: bool = False

class ActionDraft(BaseModel):
    action: str
    target: str
    text: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved: bool = False
