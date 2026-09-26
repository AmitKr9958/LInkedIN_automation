import json

import pytest

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


def test_action_gateway_enforces_run_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "dry_run", True)
    from app.approval_queue import ApprovalQueue
    from app.policy import DEFAULT_POLICY
    queue = ApprovalQueue(tmp_path / "limit.sqlite3")
    gateway = ActionGateway(queue)
    for i in range(DEFAULT_POLICY.max_actions_per_run):
        gateway.request(ActionRequest("message", f"person-{i}", {"text": "hi"}))
    with pytest.raises(RuntimeError, match="limit"):
        gateway.request(ActionRequest("message", "person-over", {"text": "hi"}))
    assert len(queue.list_pending()) == DEFAULT_POLICY.max_actions_per_run


def test_action_gateway_rejects_unsupported_action(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "dry_run", True)
    from app.approval_queue import ApprovalQueue
    queue = ApprovalQueue(tmp_path / "unsupported.sqlite3")
    with pytest.raises(ValueError, match="unsupported consequential action"):
        ActionGateway(queue).request(ActionRequest("arbitrary_sql", "person", {}))
    assert queue.list_pending() == []


def test_action_gateway_rejects_non_dict_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "dry_run", True)
    from app.approval_queue import ApprovalQueue
    queue = ApprovalQueue(tmp_path / "payload.sqlite3")
    with pytest.raises(TypeError, match="payload must be a dict"):
        ActionGateway(queue).request(ActionRequest("message", "person", "hello"))


def test_action_gateway_rejects_oversized_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "dry_run", True)
    from app.approval_queue import ApprovalQueue
    queue = ApprovalQueue(tmp_path / "large.sqlite3")
    with pytest.raises(ValueError, match="byte limit"):
        ActionGateway(queue).request(ActionRequest("message", "person", {"text": "x" * (64 * 1024)}))
