from app.history import History

def test_job_history_upsert_and_blank_url(tmp_path):
    h = History(str(tmp_path / "jobs.sqlite3"))
    job = {"title":"Power BI Developer","company":"Example","location":"Gurgaon","url":"https://example.test/job/1"}
    h.upsert_job(job, 80, ["target role"])
    h.upsert_job({**job, "location":"Noida"}, 90, ["preferred location"])
    rows = h.recent()
    assert len(rows) == 1
    assert rows[0][2] == "Noida"
    h.upsert_job({"title":"Another","company":"X"}, 10, [])
    assert len(h.recent()) == 2
    assert h.get_by_url(job["url"])[2] == "Noida"
    assert h.get_by_url("") is None


def test_job_history_persists_posting_age_and_prunes_stale_rows(tmp_path):
    h = History(str(tmp_path / "jobs.sqlite3"))
    h.upsert_job(
        {
            "title": "Fresh",
            "company": "Example",
            "location": "Delhi, India",
            "url": "https://example.test/job/fresh",
            "posted_hours": 1.5,
            "posted_text": "1 hour ago",
        },
        90,
        ["fresh"],
    )
    h.upsert_job(
        {
            "title": "Stale",
            "company": "Example",
            "location": "Delhi, India",
            "url": "https://example.test/job/stale",
            "posted_hours": 5,
            "posted_text": "5 hours ago",
        },
        70,
        ["stale"],
    )

    removed = h.cleanup_older_than_hours(4)

    assert removed == 1
    assert h.get_by_url("https://example.test/job/fresh") is not None
    assert h.get_by_url("https://example.test/job/stale") is None


def test_job_history_prunes_unknown_posting_age(tmp_path):
    h = History(str(tmp_path / "jobs.sqlite3"))
    h.upsert_job(
        {
            "title": "Unknown age",
            "company": "Example",
            "location": "Delhi, India",
            "url": "https://example.test/job/unknown",
        },
        80,
        ["unknown"],
    )
    assert h.cleanup_older_than_hours(6) == 1
    assert h.get_by_url("https://example.test/job/unknown") is None


def test_job_history_time_aware_pruning(tmp_path):
    from datetime import datetime, timedelta, timezone
    h = History(str(tmp_path / "jobs.sqlite3"))
    now = datetime.now(timezone.utc)
    import sqlite3
    with sqlite3.connect(h.path) as db:
        db.execute(
            "INSERT INTO job_history(title,company,url,first_seen,posted_hours,posted_at) VALUES(?,?,?,?,?,?)",
            ("Old", "Example", "https://example.test/old", now.isoformat(), 1.0, (now - timedelta(hours=7)).isoformat()),
        )
        db.commit()
    assert h.cleanup_older_than_hours(6) == 1
    assert h.get_by_url("https://example.test/old") is None
