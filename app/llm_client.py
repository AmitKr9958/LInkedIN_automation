from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from .config import settings


class LLMError(RuntimeError):
    """Raised when the configured LLM provider cannot complete a request."""


def _provider() -> str:
    return str(settings.llm_provider or "none").strip().lower()


def is_configured() -> bool:
    provider = _provider()
    if provider == "none":
        return False
    if provider == "9router":
        return bool(settings.llm_base_url and settings.llm_model)
    return bool(settings.llm_api_key and settings.llm_base_url and settings.llm_model)


def provider_status() -> dict[str, Any]:
    provider = _provider()
    return {
        "provider": provider,
        "model": settings.llm_model,
        "configured": is_configured(),
        "base_url": settings.llm_base_url if provider != "none" else "",
    }


def chat_json(*, system: str, user: str, temperature: float = 0.2, max_tokens: int = 2400) -> dict[str, Any]:
    if not is_configured():
        raise LLMError(
            "AI is not configured. Set LLM_PROVIDER=openrouter (or 9router), "
            "LLM_MODEL, and the provider key/base URL in your local .env."
        )
    endpoint = settings.llm_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.llm_model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    if _provider() == "openrouter":
        headers["HTTP-Referer"] = settings.llm_http_referer
        headers["X-Title"] = settings.llm_app_name
    req = request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=settings.llm_timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise LLMError(f"LLM provider returned HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise LLMError(f"Could not reach LLM provider: {exc.reason}") from exc
    except TimeoutError as exc:
        raise LLMError("LLM provider request timed out") from exc
    try:
        envelope = json.loads(raw)
        content = envelope["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise LLMError("LLM provider returned an unexpected response format") from exc
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    content = str(content).strip()
    if not content.startswith("{") or not content.endswith("}"):
        raise LLMError("LLM returned non-JSON content for a JSON-only request")
    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError("LLM returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise LLMError("LLM JSON response must be an object")
    return result
