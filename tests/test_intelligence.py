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
    job = JobRecord("Power BI Developer", "Example", "Gurgaon", posted_text="12 hours ago")
    ranked = rank_jobs([job], DEFAULT_JOB_PREFERENCES)
    assert "recent posting" in ranked[0]["reasons"]


def test_stale_job_gets_negative_recency_signal():
    job = JobRecord("Power BI Developer", "Example", "Gurgaon", posted_text="3 days ago")
    ranked = rank_jobs([job], DEFAULT_JOB_PREFERENCES)
    assert "outside posting window" in ranked[0]["reasons"]
