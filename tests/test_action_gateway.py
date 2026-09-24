import json

from app.action_gateway import ActionGateway, ActionRequest
from app.config import settings


def test_action_gateway_always_queues(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "dry_run", True)
    from app.approval_queue import ApprovalQueue
    queue = ApprovalQueue(tmp_path / "actions.sqlite3")
    item = ActionGateway(queue).request(ActionRequest("message", "person", {"text": "hello"}))
    assert item
    assert queue.list_pending()[0].action == "dry_run:message"
    assert json.loads(queue.list_pending()[0].payload)["text"] == "hello"
