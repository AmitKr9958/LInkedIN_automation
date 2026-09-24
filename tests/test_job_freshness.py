from dataclasses import dataclass

from app.skill_runtime import _filter_jobs_by_freshness


@dataclass
class FakeJob:
    posted_hours: float | None


def test_default_job_freshness_keeps_jobs_within_48_hours():
    result = _filter_jobs_by_freshness([
        FakeJob(2),
        FakeJob(48),
        FakeJob(48.01),
        FakeJob(None),
    ])
    assert [job.posted_hours for job in result] == [2, 48, None]


def test_job_freshness_can_be_disabled():
    jobs = [FakeJob(10), FakeJob(100)]
    assert _filter_jobs_by_freshness(jobs, None) == jobs


def test_job_freshness_custom_window():
    result = _filter_jobs_by_freshness([FakeJob(23), FakeJob(24), FakeJob(24.1)], 24)
    assert [job.posted_hours for job in result] == [23, 24]
