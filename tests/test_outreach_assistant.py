from app.approval_queue import ApprovalItem
from app.outreach_assistant import OutreachValidationError, validate_manual_outreach


def _item(target="https://www.linkedin.com/in/example/", message="Hello, I would like to connect."):
    return ApprovalItem("id-1", "message", target, message, "approved", "2026-10-03T00:00:00+00:00")


def test_valid_manual_outreach_packet():
    packet = validate_manual_outreach(_item())
    assert packet.review_id == "id-1"
    assert packet.target.endswith("/example/")
    assert packet.message.startswith("Hello")


def test_manual_outreach_rejects_non_linkedin_target():
    try:
        validate_manual_outreach(_item("https://example.com/person"))
        assert False, "expected validation error"
    except OutreachValidationError as exc:
        assert "linkedin.com" in str(exc)


def test_manual_outreach_rejects_non_profile_target():
    try:
        validate_manual_outreach(_item("https://www.linkedin.com/jobs/view/123"))
        assert False, "expected validation error"
    except OutreachValidationError as exc:
        assert "/in/" in str(exc)


def test_manual_outreach_rejects_pending_item():
    item = _item()
    item.status = "pending"
    try:
        validate_manual_outreach(item)
        assert False, "expected validation error"
    except OutreachValidationError as exc:
        assert "approved" in str(exc)


def test_manual_outreach_rejects_oversized_message():
    try:
        validate_manual_outreach(_item(message="x" * 1901))
        assert False, "expected validation error"
    except OutreachValidationError as exc:
        assert "1900" in str(exc)


def test_valid_manual_connection_request_packet():
    item = ApprovalItem(
        "id-2",
        "connection_request",
        "https://www.linkedin.com/in/example/",
        "Hello, I noticed your team is hiring for a Power BI role and would like to connect.",
        "approved",
        "2026-10-03T00:00:00+00:00",
    )
    packet = validate_manual_outreach(item)
    assert packet.review_id == "id-2"
    assert "Power BI" in packet.message
