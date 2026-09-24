from app.job_normalize import normalize_job_url, dedupe_jobs

def test_normalizes_tracking_parameters():
    assert normalize_job_url("HTTPS://Example.com/jobs/1/?utm_source=x&trk=abc") == "https://example.com/jobs/1"

def test_dedupes_jobs():
    rows=[{"url":"https://example.com/jobs/1?utm_source=a"},{"url":"https://example.com/jobs/1?trk=b"}]
    assert len(dedupe_jobs(rows)) == 1
