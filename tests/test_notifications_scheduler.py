from app.notifications import FileNotificationProvider, build_daily_report
from app.scheduler import ReadOnlyScheduler


def test_daily_report_contains_job_fields(tmp_path):
    report = build_daily_report([{"title":"Power BI Developer","company":"EXL","location":"Gurgaon","posted":"1 day ago","applicant_count":12}])
    path = tmp_path / "report.json"
    FileNotificationProvider(path).send(report)
    assert "Power BI Developer" in path.read_text(encoding="utf-8")


def test_scheduler_minimum_interval():
    assert ReadOnlyScheduler(60).metadata().interval_minutes == 60
