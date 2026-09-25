from __future__ import annotations

from dataclasses import dataclass, field

@dataclass
class UserJobPreferences:
    keywords: list[str] = field(default_factory=lambda: [
        "Power BI Developer",
        "Power BI",
        "Business Intelligence",
        "Data Analyst",
        "BI Developer",
        "Reporting Analyst",
    ])
    locations: list[str] = field(default_factory=lambda: ["Delhi", "Gurgaon", "Noida", "Jaipur"])
    posted_within_hours: int = 48
    exclude_internships: bool = True
    exclude_fresher_roles: bool = True
    easy_apply_preferred: bool = True
    remote_only_if_explicit: bool = True
    min_experience_years: int = 5
    max_experience_years: int = 12
    preferred_applicant_count: int = 25
    acceptable_applicant_count: int = 50

DEFAULT_JOB_PREFERENCES = UserJobPreferences()
