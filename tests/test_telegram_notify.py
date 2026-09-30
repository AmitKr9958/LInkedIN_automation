from app import telegram_notify


def test_telegram_message_skips_when_not_configured(monkeypatch):
    monkeypatch.setattr(telegram_notify.settings, "telegram_notifications_enabled", False)
    monkeypatch.setattr(telegram_notify.settings, "telegram_bot_token", None)
    monkeypatch.setattr(telegram_notify.settings, "telegram_chat_id", None)

    assert telegram_notify.send_telegram_message("hello") is False


def test_agent_completion_builds_success_message(monkeypatch):
    monkeypatch.setattr(telegram_notify.settings, "telegram_notifications_enabled", True)
    monkeypatch.setattr(telegram_notify.settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(telegram_notify.settings, "telegram_chat_id", "123")

    captured = {}

    def fake_send(message):
        captured["message"] = message
        return True

    monkeypatch.setattr(telegram_notify, "send_telegram_message", fake_send)

    assert telegram_notify.notify_agent_completion(
        success=True,
        duration_seconds=42.5,
        jobs=6,
        new_jobs=5,
        tracked_jobs=5,
        hiring_posts=3,
        recruiter_targets=0,
        connection_drafts=0,
    )
    assert "✅ COMPLETED" in captured["message"]
    assert "Jobs found: 6" in captured["message"]
    assert "New jobs: 5" in captured["message"]
    assert "Duration: 42.5s" in captured["message"]


def test_agent_completion_builds_failure_message(monkeypatch):
    captured = {}

    def fake_send(message):
        captured["message"] = message
        return True

    monkeypatch.setattr(telegram_notify, "send_telegram_message", fake_send)

    assert telegram_notify.notify_agent_completion(
        success=False,
        duration_seconds=12.0,
        error_message="RuntimeError: LinkedIn session is not verified",
    )
    assert "❌ FAILED" in captured["message"]
    assert "LinkedIn session is not verified" in captured["message"]
