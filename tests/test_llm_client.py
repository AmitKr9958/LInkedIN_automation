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

def test_openrouter_payload_includes_free_fallback(monkeypatch):
    import json
    import app.llm_client as client

    monkeypatch.setattr(client.settings, "llm_provider", "openrouter")
    monkeypatch.setattr(client.settings, "llm_model", "qwen/qwen3.8-27b:free")
    monkeypatch.setattr(client.settings, "llm_api_key", "test")
    captured = {}

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return b'{"choices":[{"message":{"content":"{\"ok\":true}"}}]}'

    def fake_urlopen(req, timeout):
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return Response()

    monkeypatch.setattr(client.request, "urlopen", fake_urlopen)
    result = client.chat_json(system="s", user="u")

    assert result == {"ok": True}
    assert captured["payload"]["models"] == [
        "qwen/qwen3.8-27b:free",
        "openrouter/free",
    ]
