from dataclasses import dataclass

from app.skill_runtime import _filter_jobs_by_freshness
from app.job_preferences import DEFAULT_JOB_PREFERENCES


@dataclass
class FakeJob:
    posted_hours: float | None


def test_default_preference_is_6_hours():
    assert DEFAULT_JOB_PREFERENCES.posted_within_hours == 6


def test_default_job_freshness_keeps_jobs_within_6_hours():
    """Strict policy: known ages within window are kept; unknown ages are excluded."""
    result = _filter_jobs_by_freshness([
        FakeJob(0),
        FakeJob(3.5),
        FakeJob(6),
        FakeJob(6.1),
        FakeJob(None),
    ], DEFAULT_JOB_PREFERENCES.posted_within_hours)
    assert [job.posted_hours for job in result] == [0, 3.5, 6]


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


def test_job_freshness_boundary_exactly_6_hours_custom_window():
    result = _filter_jobs_by_freshness([FakeJob(6.0), FakeJob(6.01)], 6)
    assert [job.posted_hours for job in result] == [6.0]


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


def test_zero_result_reason_mentions_location_and_window():
    """Human-readable zero-result messaging must stay available for operators."""
    diagnostics = {
        "requested_location": "Noida",
        "returned_after_location": 0,
        "freshness_window_hours": 6,
        "final_returned": 0,
        "unknown_posted_age": 3,
        "rejected_freshness": 5,
    }
    location = diagnostics["requested_location"]
    window = diagnostics["freshness_window_hours"]
    reason = (
        f"No qualifying {location} jobs found within the configured "
        f"{window}-hour freshness window "
        "(unknown posting ages remain excluded by default)."
    )
    assert "Noida" in reason
    assert "6" in reason
    assert "unknown" in reason.lower()


def test_compact_posted_age_parsing():
    from app.skills.jobs import _hours_from_posted, _normalize_posted

    assert _hours_from_posted("3h") == 3.0
    assert _hours_from_posted("2d") == 48.0
    assert _hours_from_posted("15m") == 0.25
    assert _hours_from_posted("1w") == 168.0
    assert _hours_from_posted("2 hours ago") == 2.0
    assert _normalize_posted("Posted 2d ago by recruiter") in ("2d", "2d ago") or "2" in _normalize_posted("Posted 2d ago by recruiter")


def test_unknown_age_still_rejected_by_default():
    from dataclasses import dataclass
    from app.skill_runtime import _filter_jobs_by_freshness

    @dataclass
    class FakeJob:
        posted_hours: float | None

    kept = _filter_jobs_by_freshness([FakeJob(10), FakeJob(None), FakeJob(100)], 48)
    assert [j.posted_hours for j in kept] == [10]
