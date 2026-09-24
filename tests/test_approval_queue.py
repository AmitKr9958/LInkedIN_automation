from app.approval_queue import ApprovalQueue

def test_queue_lifecycle(tmp_path):
    q=ApprovalQueue(str(tmp_path/"db.sqlite3"))
    item=q.add("message","person-1","hello")
    assert q.list_pending()[0].id == item
    q.decide(item,True)
    assert q.list_pending() == []
