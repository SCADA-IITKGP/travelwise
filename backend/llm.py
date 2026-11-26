"""Verified hosted-model client with runtime model selection, key-level queueing, and bounded retries."""

import asyncio
import re
import ssl
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .config import (
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
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
AVAILABLE_MODELS = [
    {
        "id": "evidence-only",
        "label": "Evidence-only (No model)",
        "mode": "mock",
        "model": None,
    },
    {
        "id": DEFAULT_LLM_MODEL,
        "label": f"{DEFAULT_LLM_MODEL} (Hosted)",
        "mode": "hosted",
        "model": DEFAULT_LLM_MODEL,
    },
]

_provider_lock = asyncio.Lock()
_call_times: deque[float] = deque()
_mode = LLM_MODE
_base_url = LLM_BASE_URL or DEFAULT_LLM_BASE_URL
_api_key = LLM_API_KEY
_model = LLM_MODEL or DEFAULT_LLM_MODEL
_ca_cert_file = LLM_CA_CERT_FILE
_last_success_at: str | None = None
_last_error: str | None = None
_last_status_code: int | None = None
_calls = 0
_retries = 0


class LLMError(RuntimeError):
    pass


def _chat_url() -> str:
    """_base_url is the assigned HTTPS API base, normally ending in /v1."""
    base = (_base_url or "").rstrip("/")
    if not base.startswith("https://"):
        raise LLMError("Hosted API must use HTTPS with certificate verification enabled.")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _model_list_url() -> str:
    base = (_base_url or "").rstrip("/")
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")]
    return base + "/models"


def _verify_certificate() -> str:
    if not _ca_cert_file:
        raise LLMError("Hosted mode requires the CA certificate assigned to this API endpoint (e.g. vm04-ca.crt).")
    cert_path = Path(_ca_cert_file)
    if not cert_path.is_file():
        raise LLMError(f"The configured hosted API CA certificate file was not found: {cert_path}")
    try:
        ssl.create_default_context(cafile=str(cert_path))
    except (OSError, ssl.SSLError) as exc:
        raise LLMError("The configured hosted API CA certificate could not be loaded.") from exc
    return str(cert_path)


def is_configured() -> bool:
    return bool(_base_url and _api_key and _model and _ca_cert_file)


def current_mode() -> str:
    return _mode


def select_model(
    *,
    selection: str | None = None,
    mode: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    ca_cert_file: str | None = None,
) -> dict:
    """Update the active model selection and optional hosted connection settings in memory."""
    global _mode, _base_url, _api_key, _model, _ca_cert_file, _last_error

    if base_url is not None and base_url.strip():
        cleaned = base_url.strip().rstrip("/")
        if not cleaned.startswith("https://"):
            raise ValueError("Hosted API base URL must use HTTPS.")
        _base_url = cleaned
    if api_key is not None and api_key.strip():
        _api_key = api_key.strip()
    if ca_cert_file is not None and ca_cert_file.strip():
        _ca_cert_file = ca_cert_file.strip()
    if model is not None and model.strip():
        _model = model.strip()

    target_mode = mode.strip().lower() if mode else None
    if selection:
        sel = selection.strip()
        if sel.lower() in {"evidence-only", "mock", "none"}:
            target_mode = "mock"
        else:
            _model = sel
            target_mode = target_mode or "hosted"

    if target_mode == "mock":
        _mode = "mock"
    elif target_mode == "hosted":
        if not is_configured():
            missing = [
                name
                for name, present in (
                    ("base_url", bool(_base_url)),
                    ("api_key", bool(_api_key)),
                    ("model", bool(_model)),
                    ("ca_cert_file", bool(_ca_cert_file)),
                )
                if not present
            ]
            raise ValueError(f"Hosted model { _model or DEFAULT_LLM_MODEL } requires: {', '.join(missing)}.")
        _verify_certificate()
        _mode = "hosted"
    elif target_mode is not None:
        raise ValueError("LLM mode must be 'mock' or 'hosted'.")

    _last_error = None
    return status()


def status() -> dict:
    now = time.monotonic()
    while _call_times and now - _call_times[0] >= 60:
        _call_times.popleft()
    parsed = urlsplit(_base_url) if _base_url else None
    configured = is_configured()
    active_selection = _model if (_mode == "hosted" and configured) else "evidence-only"
    models = list(AVAILABLE_MODELS)
    if _model and all(m["id"] != _model for m in models):
        models.append({"id": _model, "label": f"{_model} (Hosted)", "mode": "hosted", "model": _model})
    return {
        "mode": _mode,
        "configured": configured,
        "active_selection": active_selection,
        "available_models": models,
        "endpoint_url": _base_url or None,
        "endpoint_host": parsed.hostname if parsed else None,
        "model": _model or DEFAULT_LLM_MODEL,
        "max_tokens": LLM_MAX_TOKENS,
        "ca_certificate_configured": bool(_ca_cert_file),
        "ca_certificate_path": _ca_cert_file or None,
        "calls_in_last_minute": len(_call_times),
        "local_limit_per_minute": MAX_CALLS_PER_MINUTE,
        "queued_or_active": _provider_lock.locked(),
        "total_calls": _calls,
        "retries": _retries,
        "last_success_at": _last_success_at,
        "last_status_code": _last_status_code,
        "last_error": _last_error,
    }


async def _request(method: str, url: str, *, json_body: dict | None = None, model_override: str | None = None) -> httpx.Response:
    global _calls, _retries, _last_error, _last_status_code, _last_success_at
    active_model = model_override or _model
    if not (_base_url and _api_key and active_model):
        raise LLMError("Hosted mode requires LLM_BASE_URL, LLM_API_KEY and LLM_MODEL.")
    verify = _verify_certificate()
    headers = {"Authorization": f"Bearer {_api_key}"}
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


async def generate(system_prompt: str, user_prompt: str, model_override: str | None = None) -> str:
    if _mode != "hosted":
        return (
            "No hosted language model is configured. I can only use retrieved policy evidence; "
            "connect an approved provider before enabling generated responses."
        )

    # Conservative character estimate prevents sending oversized prompts to the
    # fixed 8,192-token context endpoint without adding an unpinned tokenizer.
    max_prompt_chars = (MAX_CONTEXT_TOKENS - LLM_MAX_TOKENS) * 3
    if len(system_prompt) + len(user_prompt) > max_prompt_chars:
        raise LLMError("Hosted model request exceeds the configured context budget.")

    active_model = model_override or _model
    body = {
        "model": active_model,
        "temperature": 0.1,
        "max_tokens": LLM_MAX_TOKENS,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    try:
        response = await _request("POST", _chat_url(), json_body=body, model_override=active_model)
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise LLMError("Hosted API returned an empty or unsupported response.")
        cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()
        if not cleaned:
            raise LLMError("Hosted API returned an empty or unsupported response.")
        return cleaned
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
    return {"reachable": True, "model_available": _model in model_ids, "configured_model": _model}
