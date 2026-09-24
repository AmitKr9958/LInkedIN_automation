from app.intelligence import JobRecord, rank_jobs
from app.job_preferences import DEFAULT_JOB_PREFERENCES

def test_power_bi_gurgaon_job_ranks_high():
    job=JobRecord("Senior Power BI Developer","Example","Gurgaon",easy_apply=True)
    ranked=rank_jobs([job],DEFAULT_JOB_PREFERENCES)
    assert ranked[0]["score"] > 50

def test_internship_is_excluded():
    job=JobRecord("Power BI Intern","Example","Gurgaon")
    ranked=rank_jobs([job],DEFAULT_JOB_PREFERENCES)
    assert ranked[0]["score"] < 0
