from types import SimpleNamespace

from app.skill_runtime import _filter_jobs_by_preference_exclusions


def job(title: str, text: str = ""):
    return SimpleNamespace(title=title, text=text, company="Example", location="India")


def test_rejects_internship_jobs():
    rows = [job("Healthcare Data Analyst Intern | Entry Level | Fresher")]
    diagnostics = {}
    assert _filter_jobs_by_preference_exclusions(rows, diagnostics) == []
    assert diagnostics["rejected_internship"] == 1


def test_rejects_fresher_and_entry_level_jobs():
    rows = [
        job("Data Analyst", "Fresher role; 0-1 years"),
        job("Data Analyst", "Entry-level position"),
    ]
    diagnostics = {}
    assert _filter_jobs_by_preference_exclusions(rows, diagnostics) == []
    assert diagnostics["rejected_fresher"] == 2


def test_keeps_non_fresher_target_job():
    rows = [job("Senior Data Analyst", "5+ years experience")]
    diagnostics = {}
    assert _filter_jobs_by_preference_exclusions(rows, diagnostics) == rows
    assert diagnostics["rejected_internship"] == 0
    assert diagnostics["rejected_fresher"] == 0
