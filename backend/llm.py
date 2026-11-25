"""Verified hosted-model client with key-level queueing and bounded retries."""

import asyncio
import ssl
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_CA_CERT_FILE,
    LLM_MAX_TOKENS,
    LLM_MODE,
    LLM_MODEL,
    LLM_TIMEOUT_SECONDS,
)

MAX_CALLS_PER_MINUTE = 55  # Leave headroom under the provider's shared 60/min key limit.
MAX_CONTEXT_TOKENS = 8192
RETRY_DELAYS = (2, 4, 8)
_provider_lock = asyncio.Lock()
_call_times: deque[float] = deque()
_last_success_at: str | None = None
_last_error: str | None = None
_last_status_code: int | None = None
_calls = 0
_retries = 0


class LLMError(RuntimeError):
    pass


def _chat_url() -> str:
    """LLM_BASE_URL is the assigned HTTPS API base, normally ending in /v1."""
    base = LLM_BASE_URL.rstrip("/")
    if not base.startswith("https://"):
        raise LLMError("Hosted API must use HTTPS with certificate verification enabled.")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _model_list_url() -> str:
    return LLM_BASE_URL.rstrip("/") + "/models"


def _verify_certificate() -> str | bool:
    if not LLM_CA_CERT_FILE:
        raise LLMError("Hosted mode requires the CA certificate assigned to this API endpoint.")
    cert_path = Path(LLM_CA_CERT_FILE)
    if not cert_path.is_file():
        raise LLMError("The configured hosted API CA certificate file was not found.")
    try:
        ssl.create_default_context(cafile=str(cert_path))
    except (OSError, ssl.SSLError) as exc:
        raise LLMError("The configured hosted API CA certificate could not be loaded.") from exc
    return str(cert_path)


def status() -> dict:
    now = time.monotonic()
    while _call_times and now - _call_times[0] >= 60:
        _call_times.popleft()
    parsed = urlsplit(LLM_BASE_URL) if LLM_BASE_URL else None
    return {
        "mode": LLM_MODE,
        "configured": bool(LLM_BASE_URL and LLM_API_KEY and LLM_MODEL and LLM_CA_CERT_FILE),
        "endpoint_host": parsed.hostname if parsed else None,
        "model": LLM_MODEL or None,
        "ca_certificate_configured": bool(LLM_CA_CERT_FILE),
        "calls_in_last_minute": len(_call_times),
        "local_limit_per_minute": MAX_CALLS_PER_MINUTE,
        "queued_or_active": _provider_lock.locked(),
        "total_calls": _calls,
        "retries": _retries,
        "last_success_at": _last_success_at,
        "last_status_code": _last_status_code,
        "last_error": _last_error,
    }


async def _request(method: str, url: str, *, json_body: dict | None = None) -> httpx.Response:
    global _calls, _retries, _last_error, _last_status_code, _last_success_at
    if not (LLM_BASE_URL and LLM_API_KEY and LLM_MODEL):
        raise LLMError("Hosted mode requires LLM_BASE_URL, LLM_API_KEY and LLM_MODEL.")
    verify = _verify_certificate()
    headers = {"Authorization": f"Bearer {LLM_API_KEY}"}
    if json_body is not None:
        headers["Content-Type"] = "application/json"

    # One in-flight request per process and key, as required by the group endpoint.
    async with _provider_lock:
        for attempt in range(len(RETRY_DELAYS) + 1):
            now = time.monotonic()
            while _call_times and now - _call_times[0] >= 60:
                _call_times.popleft()
            if len(_call_times) >= MAX_CALLS_PER_MINUTE:
                await asyncio.sleep(max(0.1, 60 - (now - _call_times[0])))
            _call_times.append(time.monotonic())
            _calls += 1
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(LLM_TIMEOUT_SECONDS), verify=verify
                ) as client:
                    response = await client.request(method, url, headers=headers, json=json_body)
                _last_status_code = response.status_code
                if response.status_code in (429, 503) and attempt < len(RETRY_DELAYS):
                    _retries += 1
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                    continue
                response.raise_for_status()
                _last_error = None
                from datetime import datetime, timezone
                _last_success_at = datetime.now(timezone.utc).isoformat()
                return response
            except httpx.HTTPStatusError as exc:
                _last_error = f"http_{exc.response.status_code}"
                raise LLMError(f"Hosted model returned HTTP {exc.response.status_code}.") from exc
            except httpx.TimeoutException as exc:
                _last_error = "timeout"
                raise LLMError("Hosted model request timed out.") from exc
            except httpx.RequestError as exc:
                _last_error = type(exc).__name__
                raise LLMError(f"Hosted model connection failed: {type(exc).__name__}.") from exc
        raise LLMError("Hosted model retry limit reached.")


async def generate(system_prompt: str, user_prompt: str) -> str:
    if LLM_MODE != "hosted":
        return (
            "No hosted language model is configured. I can only use retrieved policy evidence; "
            "connect an approved provider before enabling generated responses."
        )

    # Conservative character estimate prevents sending oversized prompts to the
    # fixed 8,192-token context endpoint without adding an unpinned tokenizer.
    max_prompt_chars = (MAX_CONTEXT_TOKENS - LLM_MAX_TOKENS) * 3
    if len(system_prompt) + len(user_prompt) > max_prompt_chars:
        raise LLMError("Hosted model request exceeds the configured context budget.")

    body = {
        "model": LLM_MODEL,
        "temperature": 0.1,
        "max_tokens": LLM_MAX_TOKENS,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    try:
        response = await _request("POST", _chat_url(), json_body=body)
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise LLMError("Hosted API returned an empty or unsupported response.")
        return content.strip()
    except LLMError:
        raise
    except (KeyError, ValueError, TypeError) as exc:
        raise LLMError(f"Hosted model response error: {type(exc).__name__}.") from exc


async def health_check() -> dict:
    """Verify endpoint, key and CA via the non-inference /models endpoint."""
    response = await _request("GET", _model_list_url())
    try:
        payload = response.json()
        model_ids = [item.get("id") for item in payload.get("data", []) if isinstance(item, dict)]
    except (ValueError, AttributeError, TypeError):
        model_ids = []
    return {"reachable": True, "model_available": LLM_MODEL in model_ids, "configured_model": LLM_MODEL}
