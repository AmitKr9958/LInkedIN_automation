from dataclasses import dataclass

from app.skill_runtime import _filter_jobs_by_freshness
from app.job_preferences import DEFAULT_JOB_PREFERENCES


@dataclass
class FakeJob:
    posted_hours: float | None


def test_default_preference_is_1_hour():
    assert DEFAULT_JOB_PREFERENCES.posted_within_hours == 1


def test_default_job_freshness_keeps_jobs_within_1_hour():
    """Strict policy: known ages within window are kept; unknown ages are excluded."""
    result = _filter_jobs_by_freshness([
        FakeJob(0),
        FakeJob(0.99),
        FakeJob(1),
        FakeJob(1.01),
        FakeJob(None),
    ], DEFAULT_JOB_PREFERENCES.posted_within_hours)
    assert [job.posted_hours for job in result] == [0, 0.99, 1]


def test_job_freshness_excludes_unknown_age_by_default():
    result = _filter_jobs_by_freshness([FakeJob(10), FakeJob(None), FakeJob(100)], 48)
    assert [job.posted_hours for job in result] == [10]


def test_job_freshness_can_include_unknown_age():
    result = _filter_jobs_by_freshness(
        [FakeJob(10), FakeJob(None), FakeJob(100)],
        48,
        include_unknown_age=True,
    )
    assert [job.posted_hours for job in result] == [10, None]


def test_job_freshness_can_be_disabled():
    jobs = [FakeJob(10), FakeJob(100), FakeJob(None)]
    assert _filter_jobs_by_freshness(jobs, None) == jobs


def test_job_freshness_custom_window():
    result = _filter_jobs_by_freshness([FakeJob(23), FakeJob(24), FakeJob(24.1)], 24)
    assert [job.posted_hours for job in result] == [23, 24]


def test_job_freshness_boundary_exactly_48():
    result = _filter_jobs_by_freshness([FakeJob(48.0), FakeJob(48.01)], 48)
    assert [job.posted_hours for job in result] == [48.0]


def test_job_freshness_rejects_old_relative_ages():
    # 2 weeks ≈ 336h, 4 months ≈ 2880h
    result = _filter_jobs_by_freshness(
        [FakeJob(336), FakeJob(2880), FakeJob(1)],
        48,
    )
    assert [job.posted_hours for job in result] == [1]


def test_job_freshness_reports_rejection_counts():
    diagnostics = {}
    result = _filter_jobs_by_freshness(
        [FakeJob(2), FakeJob(100), FakeJob(None)], 48, diagnostics=diagnostics
    )
    assert [job.posted_hours for job in result] == [2]
    assert diagnostics["freshness_window_hours"] == 48
    assert diagnostics["rejected_freshness"] == 2  # 100h + unknown
    assert diagnostics["unknown_posted_age"] == 1
    assert diagnostics["returned_after_freshness"] == 1
    assert diagnostics["include_unknown_age"] is False


def test_job_freshness_disabled_reports_open_window():
    diagnostics = {}
    jobs = [FakeJob(10), FakeJob(100)]
    assert _filter_jobs_by_freshness(jobs, None, diagnostics=diagnostics) == jobs
    assert diagnostics["freshness_window_hours"] is None
