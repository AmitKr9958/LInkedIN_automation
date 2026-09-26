from dataclasses import dataclass

from app.job_preferences import DEFAULT_JOB_PREFERENCES, DEFAULT_JOB_SEARCH_QUERY
from app.skill_runtime import _filter_jobs_by_title, _job_title_matches_preferences


@dataclass
class FakeJob:
    title: str
    text: str = ""
    company: str = ""


def test_default_search_window_is_one_hour():
    assert DEFAULT_JOB_PREFERENCES.posted_within_hours == 1


def test_default_search_query_contains_target_roles():
    assert "Senior Data Analyst" in DEFAULT_JOB_SEARCH_QUERY
    assert "Senior Power BI Developer" in DEFAULT_JOB_SEARCH_QUERY
    assert "Power BI Lead" in DEFAULT_JOB_SEARCH_QUERY
    assert "Assistant Manager - BI" in DEFAULT_JOB_SEARCH_QUERY
    assert "Reporting Lead" in DEFAULT_JOB_SEARCH_QUERY


def test_target_titles_match():
    titles = [
        "Senior Data Analyst",
        "Senior Power BI Developer",
        "Power BI Lead",
        "Lead Power BI Developer",
        "Assistant Manager - BO/BI Developer",
        "Reporting Lead",
        "BI Developer",
        "Business Intelligence Analyst",
        "MIS Manager",
    ]
    assert all(_job_title_matches_preferences(title) for title in titles)


def test_unrelated_assistant_manager_does_not_match():
    assert not _job_title_matches_preferences("Assistant Manager - BFS Direct")


def test_unrelated_manager_does_not_match():
    assert not _job_title_matches_preferences("Finance Manager")


def test_title_filter_keeps_only_target_roles():
    jobs = [
        FakeJob("Senior Data Analyst"),
        FakeJob("Power BI Lead"),
        FakeJob("Assistant Manager - Finance"),
        FakeJob("Finance Manager"),
    ]
    result = _filter_jobs_by_title(jobs)
    assert [job.title for job in result] == ["Senior Data Analyst", "Power BI Lead"]
