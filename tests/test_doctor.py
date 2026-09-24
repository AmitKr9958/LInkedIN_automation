from app.doctor import run_doctor


def test_doctor_has_core_checks():
    checks = run_doctor()
    names = {check.name for check in checks}
    assert "policy" in names
    assert "browser-profile" in names
    assert "approval" in names
    assert all(hasattr(check, "blocking") for check in checks)


def test_doctor_dry_run_is_non_blocking():
    check = next(x for x in run_doctor() if x.name == "dry-run")
    assert check.blocking is False
