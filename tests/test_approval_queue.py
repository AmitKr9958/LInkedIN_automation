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
