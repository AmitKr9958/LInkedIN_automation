from app.selftest import run_selftest


def test_selftest_has_core_modules():
    results = run_selftest()
    names = {result.name for result in results}
    assert "skill-registry" in names
    assert all(result.ok for result in results)
