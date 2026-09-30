from app.llm_client import _parse_json_object


def test_parse_json_object_accepts_plain_json():
    assert _parse_json_object('{"headline_options":["A","B","C"]}') == {
        "headline_options": ["A", "B", "C"]
    }


def test_parse_json_object_accepts_fenced_json():
    result = _parse_json_object('Here is the result:\n\n```json\n{"ok":true}\n```')
    assert result == {"ok": True}


def test_parse_json_object_accepts_prose_wrapped_json():
    result = _parse_json_object('I recommend the following:\n{"ok":true}\nHope this helps.')
    assert result == {"ok": True}


def test_parse_json_object_rejects_non_object_json():
    assert _parse_json_object('[1,2,3]') is None
    assert _parse_json_object('No JSON here') is None
