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
    if _provider() == "openrouter":
        # Free endpoints can temporarily exhaust their shared upstream pool.
        # Keep the configured model first, then use OpenRouter free-router fallback.
        fallback_models = [settings.llm_model]
        if settings.llm_model != "openrouter/free":
            fallback_models.append("openrouter/free")
        payload["models"] = fallback_models
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
    result = _parse_json_object(content)
    if result is not None:
        return result

    # Some OpenRouter/free models accept the request but ignore the
    # response_format hint and return prose or fenced output. Retry once with
    # an explicit JSON-only instruction and without response_format so the
    # provider can use its native fallback behavior. This remains a read-only
    # parsing retry; it does not alter any LinkedIn action or safety gate.
    retry_payload = dict(payload)
    retry_payload.pop("response_format", None)
    retry_messages = list(retry_payload["messages"])
    retry_messages[0] = {
        "role": "system",
        "content": (
            str(retry_messages[0].get("content", ""))
            + "\nReturn ONLY one valid JSON object. No markdown fences, no commentary, and no text before or after the JSON object."
        ),
    }
    retry_payload["messages"] = retry_messages
    retry_req = request.Request(
        endpoint,
        data=json.dumps(retry_payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(retry_req, timeout=settings.llm_timeout_seconds) as response:
            retry_raw = response.read().decode("utf-8")
        retry_envelope = json.loads(retry_raw)
        retry_content = retry_envelope["choices"][0]["message"]["content"]
        if isinstance(retry_content, list):
            retry_content = "".join(
                part.get("text", "") for part in retry_content if isinstance(part, dict)
            )
        retry_result = _parse_json_object(str(retry_content).strip())
    except (error.HTTPError, error.URLError, TimeoutError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise LLMError(f"LLM returned non-JSON content for a JSON-only request: retry failed ({type(exc).__name__})") from exc
    if retry_result is None:
        raise LLMError("LLM returned non-JSON content for a JSON-only request after retry")
    return retry_result


def _parse_json_object(content: str) -> dict[str, Any] | None:
    """Extract a JSON object from strict JSON, fenced JSON, or light prose wrappers."""
    text = content.strip()
    if not text:
        return None

    # Common provider/model format: fenced JSON.
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().lower().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    # Some models add a short sentence before/after the JSON. Decode the first
    # complete JSON object rather than requiring the entire response to be JSON.
    start = text.find("{")
    if start < 0:
        return None
    try:
        parsed, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
