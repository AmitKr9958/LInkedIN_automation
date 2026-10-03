import sqlite3

from app.approval_queue import ApprovalQueue


def test_queue_lifecycle(tmp_path):
    q = ApprovalQueue(str(tmp_path / "db.sqlite3"))
    item = q.add("message", "person-1", "hello")
    assert q.list_pending()[0].id == item
    assert q.decide(item, True) is True
    assert q.list_pending() == []
    assert q.decide(item, False) is False


def test_queue_rejects_invalid_values(tmp_path):
    q = ApprovalQueue(str(tmp_path / "db.sqlite3"))
    try:
        q.add("", "target", "payload")
        assert False, "expected ValueError"
    except ValueError:
        pass
    try:
        q.decide("", True)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_queue_migrates_legacy_schema(tmp_path):
    db_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.execute(
            """CREATE TABLE approval_queue(
                id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                target TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        db.commit()

    q = ApprovalQueue(str(db_path))
    with sqlite3.connect(db_path) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(approval_queue)").fetchall()}
    assert "decided_at" in columns

    item = q.add("message", "person-1", "hello")
    assert q.decide(item, True) is True


def test_queue_records_activity_history(tmp_path):
    db_path = tmp_path / "db.sqlite3"
    q = ApprovalQueue(str(db_path))
    item = q.add("message", "person-1", "hello")
    assert q.decide(item, True) is True
    assert q.decide(item, False) is False
    with sqlite3.connect(db_path) as db:
        rows = db.execute(
            "SELECT action, target, status FROM activity ORDER BY id"
        ).fetchall()
    assert ("approval_requested", "person-1", "pending") in rows
    assert ("approval_decided", "person-1", "approved") in rows
    assert len(rows) == 2


def test_queue_batch_decision_only_changes_pending_items(tmp_path):
    q = ApprovalQueue(str(tmp_path / "db.sqlite3"))
    first = q.add("connection_request", "recruiter-1", "hello")
    second = q.add("message", "recruiter-1", "hello")
    third = q.add("message", "recruiter-2", "hello")
    assert q.decide(third, False) is True
    changed = q.decide_many([first, second, third], True)
    assert changed == [first, second]
    assert q.get(first).status == "approved"
    assert q.get(second).status == "approved"
    assert q.get(third).status == "rejected"


def test_queue_lists_approved_messages_and_records_manual_completion(tmp_path):
    q = ApprovalQueue(str(tmp_path / "db.sqlite3"))
    message = q.add("message", "https://www.linkedin.com/in/recruiter/", "Hello recruiter")
    other = q.add("connection_request", "https://www.linkedin.com/in/recruiter/", "Connect")
    assert q.decide(message, True) is True
    assert q.decide(other, True) is True
    approved = q.list_approved_messages()
    assert [item.id for item in approved] == [message]
    assert q.mark_manual_sent(message) is True
    assert q.get(message).status == "manual_sent"
    assert q.list_approved_messages() == []
    assert q.mark_manual_sent(message) is False
