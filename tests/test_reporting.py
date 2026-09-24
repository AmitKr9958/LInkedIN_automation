from pathlib import Path

from app.reporting import application_rows, export_rows


def test_application_rows():
    rows = [("https://example.test/job", "Analyst", "Acme", "new", "2026-09-24T00:00:00+00:00", "")]
    assert application_rows(rows)[0]["status"] == "new"


def test_export_json_and_csv(tmp_path: Path):
    rows = [{"title": "Analyst", "company": "Acme", "score": 9}]
    json_path = export_rows(rows, tmp_path / "jobs.json")
    csv_path = export_rows(rows, tmp_path / "jobs.csv", "csv")
    assert json_path.exists()
    assert csv_path.exists()
    assert "Analyst" in json_path.read_text()
    assert "company" in csv_path.read_text()
