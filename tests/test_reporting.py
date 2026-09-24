from app.reporting import application_rows, export_rows


def test_reporting_json_and_csv(tmp_path):
    rows = [{"title": "Power BI Developer", "company": "Example"}]
    json_path = export_rows(rows, tmp_path / "jobs.json")
    csv_path = export_rows(rows, tmp_path / "jobs.csv", "csv")
    assert json_path.exists()
    assert csv_path.exists()
    assert application_rows([("u", "t", "c", "new", "now", "")])[0]["job_url"] == "u"
