from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_JOB_TITLE_KEYWORDS = [
    "Power BI Developer",
    "Senior Power BI Developer",
    "Sr Power BI Developer",
    "Power BI Lead",
    "Lead Power BI Developer",
    "Power BI Engineer",
    "Senior Data Analyst",
    "Sr Data Analyst",
    "Lead Data Analyst",
    "Data Analyst",
    "Senior BI Developer",
    "BI Developer",
    "Business Intelligence Developer",
    "BI Lead",
    "Business Intelligence Lead",
    "Senior Business Intelligence Analyst",
    "Business Intelligence Analyst",
    "Reporting Lead",
    "Senior Reporting Analyst",
    "Reporting Analyst",
    "Reporting Manager",
    "MIS Lead",
    "MIS Analyst",
    "MIS Manager",
    "Assistant Manager - BI",
    "Assistant Manager - BO/BI",
    "Assistant Manager - Data",
    "Assistant Manager - Analytics",
    "Assistant Manager - Reporting",
]

DEFAULT_JOB_SEARCH_QUERY = " OR ".join(f'"{term}"' for term in DEFAULT_JOB_TITLE_KEYWORDS)


@dataclass
class UserJobPreferences:
    keywords: list[str] = field(default_factory=lambda: list(DEFAULT_JOB_TITLE_KEYWORDS))
    locations: list[str] = field(default_factory=lambda: ["Delhi", "Gurgaon", "Noida", "Jaipur"])
    posted_within_hours: int = 1
    exclude_internships: bool = True
    exclude_fresher_roles: bool = True
    easy_apply_preferred: bool = True
    remote_only_if_explicit: bool = True
    min_experience_years: int = 5
    max_experience_years: int = 12


DEFAULT_JOB_PREFERENCES = UserJobPreferences()
