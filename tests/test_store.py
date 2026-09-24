import sqlite3

from app.store import log_activity


def test_log_activity_persists_rows(tmp_path):
    db_path = tmp_path / "activity.sqlite3"
    log_activity("unit_test", "target-1", "ok", "details", path=db_path)
    log_activity("unit_test_2", path=db_path)
    with sqlite3.connect(db_path) as db:
        rows = db.execute(
            "SELECT action, target, status, details FROM activity ORDER BY id"
        ).fetchall()
    assert rows[0] == ("unit_test", "target-1", "ok", "details")
    assert rows[1] == ("unit_test_2", "", "ok", "")
