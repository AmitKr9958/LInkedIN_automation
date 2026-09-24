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
