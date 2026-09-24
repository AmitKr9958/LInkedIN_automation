from app.doctor import run_doctor

def test_doctor_reports_core_modules():
    names = {x.name for x in run_doctor()}
    assert "module:app.browser" in names
    assert "module:app.content_skills" in names
