from app.media import build_image_prompt, build_quote_card
from app.publishing import PublishRequest, queue_publish


def test_media_prompt():
    prompt = build_image_prompt("Power BI improved refresh time by 20%.", brand_hint="clean blue")
    assert prompt.kind == "wide"
    assert "Power BI" in prompt.prompt
    assert "clean blue" in prompt.prompt


def test_quote_card():
    card = build_quote_card("Measure before you optimize.", "@amit")
    assert card.kind == "quote-card"
    assert "@amit" in card.prompt


def test_publish_is_approval_queued(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.settings.dry_run", True)
    from app.approval_queue import ApprovalQueue
    from app.agent import LinkedInAgent
    from app.action_gateway import ActionGateway
    agent = LinkedInAgent(gateway=ActionGateway(ApprovalQueue(tmp_path / "actions.sqlite3")))
    item = queue_publish(PublishRequest("Test post"), agent)
    assert item
