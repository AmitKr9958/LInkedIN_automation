from app.drafting import connection_note


def test_connection_note_contains_context():
    draft = connection_note("Amit", "Power BI Developer", ["Power BI", "SQL"])
    assert draft.kind == "connection_note"
    assert "Amit" in draft.text
    assert "Power BI Developer" in draft.text
    assert "Power BI" in draft.text


def test_connection_note_respects_linkedin_limit():
    draft = connection_note("A" * 60, "Role " * 40, ["Skill " * 10, "Other " * 10])
    assert len(draft.text) <= 300
