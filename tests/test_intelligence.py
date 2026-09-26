from app.intelligence import JobRecord, rank_jobs
from app.job_preferences import DEFAULT_JOB_PREFERENCES


def test_power_bi_gurgaon_job_ranks_high():
    job = JobRecord("Senior Power BI Developer", "Example", "Gurgaon", easy_apply=True)
    ranked = rank_jobs([job], DEFAULT_JOB_PREFERENCES)
    assert ranked[0]["score"] > 50


def test_internship_is_excluded():
    job = JobRecord("Power BI Intern", "Example", "Gurgaon")
    ranked = rank_jobs([job], DEFAULT_JOB_PREFERENCES)
    assert ranked[0]["score"] < 0


def test_recent_job_gets_recency_signal():
    job = JobRecord("Power BI Developer", "Example", "Gurgaon", posted_text="30 minutes ago")
    ranked = rank_jobs([job], DEFAULT_JOB_PREFERENCES)
    assert "recent posting" in ranked[0]["reasons"]


def test_numeric_posted_hours_drive_recency_signal():
    job = JobRecord(
        "Power BI Developer", "Example", "Gurgaon",
        posted_text="45 minutes ago", posted_hours=0.75,
    )
    ranked = rank_jobs([job], DEFAULT_JOB_PREFERENCES)
    assert "recent posting" in ranked[0]["reasons"]
    assert ranked[0]["job"]["posted_hours"] == 0.75


def test_numeric_recency_wins_over_text_estimate():
    job = JobRecord(
        "Power BI Developer", "Example", "Gurgaon",
        posted_text="3 days ago", posted_hours=0.5,
    )
    ranked = rank_jobs([job], DEFAULT_JOB_PREFERENCES)
    assert "recent posting" in ranked[0]["reasons"]


def test_unknown_recency_stays_neutral():
    job = JobRecord("Power BI Developer", "Example", "Gurgaon")
    ranked = rank_jobs([job], DEFAULT_JOB_PREFERENCES)
    assert "recent posting" not in ranked[0]["reasons"]
    assert "outside posting window" not in ranked[0]["reasons"]


def test_stale_job_gets_negative_recency_signal():
    job = JobRecord("Power BI Developer", "Example", "Gurgaon", posted_text="3 days ago")
    ranked = rank_jobs([job], DEFAULT_JOB_PREFERENCES)
    assert "outside posting window" in ranked[0]["reasons"]


def test_matching_experience_range_gets_signal():
    job = JobRecord(
        "BI Developer", "Example", "Gurgaon",
        description="Requires 6+ years of experience with Power BI.",
    )
    ranked = rank_jobs([job], DEFAULT_JOB_PREFERENCES)
    assert "experience range matches" in ranked[0]["reasons"]


def test_mismatched_experience_range_gets_negative_signal():
    job = JobRecord(
        "Data Analyst", "Example", "Gurgaon",
        description="1-2 years of experience required.",
    )
    ranked = rank_jobs([job], DEFAULT_JOB_PREFERENCES)
    assert "experience range outside preference" in ranked[0]["reasons"]


def test_bare_years_treated_as_exact_expectation():
    job = JobRecord(
        "Reporting Analyst", "Example", "Gurgaon",
        description="2 years experience preferred.",
    )
    ranked = rank_jobs([job], DEFAULT_JOB_PREFERENCES)
    assert "experience range outside preference" in ranked[0]["reasons"]
