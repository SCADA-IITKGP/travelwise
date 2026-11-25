"""Shared Capstone embedding API client with CA verification, batching, and retries."""

from datetime import datetime, timezone
import ssl
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .config import (
    DEFAULT_EMBEDDING_BASE_URL,
    DEFAULT_EMBEDDING_MODEL,
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_CA_CERT_FILE,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MAX_TOKENS,
    EMBEDDING_MODE,
    EMBEDDING_MODEL,
    EMBEDDING_TIMEOUT_SECONDS,
)

RETRY_DELAYS = (1, 2, 4)

_mode = EMBEDDING_MODE
_base_url = EMBEDDING_BASE_URL or DEFAULT_EMBEDDING_BASE_URL
_api_key = EMBEDDING_API_KEY
_model = EMBEDDING_MODEL or DEFAULT_EMBEDDING_MODEL
_ca_cert_file = EMBEDDING_CA_CERT_FILE
_last_success_at: str | None = None
_last_error: str | None = None
_last_status_code: int | None = None
_calls = 0
_retries = 0


class EmbeddingError(RuntimeError):
    pass


def _embeddings_url() -> str:
    base = (_base_url or "").rstrip("/")
    if not base.startswith("https://"):
        raise EmbeddingError("Embedding API must use HTTPS with certificate verification enabled.")
    if base.endswith("/embeddings"):
        return base
    return base + "/embeddings"


def _verify_certificate() -> str:
    if not _ca_cert_file:
        raise EmbeddingError("Embedding API requires the assigned CA certificate (e.g. vm02-ca.crt).")
    cert_path = Path(_ca_cert_file)
    if not cert_path.is_file():
        raise EmbeddingError(f"Embedding CA certificate file was not found: {cert_path}")
    try:
        ssl.create_default_context(cafile=str(cert_path))
    except (OSError, ssl.SSLError) as exc:
        raise EmbeddingError("The configured embedding CA certificate could not be loaded.") from exc
    return str(cert_path)


def is_configured() -> bool:
    return bool(
        _mode in {"hosted", "hybrid"}
        and _base_url
        and _api_key
        and _model
        and _ca_cert_file
    )


def current_mode() -> str:
    return _mode


def current_model() -> str:
    return _model


def configure(
    *,
    mode: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    ca_cert_file: str | None = None,
) -> dict:
    global _mode, _base_url, _api_key, _model, _ca_cert_file, _last_error
    if mode is not None:
        normalized = mode.strip().lower()
        if normalized not in {"tfidf", "hybrid", "hosted"}:
            raise ValueError("Embedding mode must be 'tfidf', 'hybrid', or 'hosted'.")
        _mode = normalized
    if base_url is not None and base_url.strip():
        cleaned = base_url.strip().rstrip("/")
        if not cleaned.startswith("https://"):
            raise ValueError("Embedding base URL must use HTTPS.")
        _base_url = cleaned
    if api_key is not None and api_key.strip():
        _api_key = api_key.strip()
    if model is not None and model.strip():
        _model = model.strip()
    if ca_cert_file is not None and ca_cert_file.strip():
        _ca_cert_file = ca_cert_file.strip()
    _last_error = None
    return status()


def status() -> dict:
    parsed = urlsplit(_base_url) if _base_url else None
    return {
        "mode": _mode,
        "configured": is_configured(),
        "endpoint_url": _base_url or None,
        "endpoint_host": parsed.hostname if parsed else None,
        "model": _model or DEFAULT_EMBEDDING_MODEL,
        "dimensions": EMBEDDING_DIMENSIONS,
        "batch_size": EMBEDDING_BATCH_SIZE,
        "max_tokens": EMBEDDING_MAX_TOKENS,
        "ca_certificate_configured": bool(_ca_cert_file),
        "ca_certificate_path": _ca_cert_file or None,
        "total_calls": _calls,
        "retries": _retries,
        "last_success_at": _last_success_at,
        "last_status_code": _last_status_code,
        "last_error": _last_error,
    }


def _truncate_text(text: str) -> str:
    """Keep each chunk safely within the 512-token embedding budget."""
    words = (text or "").split()
    if len(words) > EMBEDDING_MAX_TOKENS - 32:
        words = words[: EMBEDDING_MAX_TOKENS - 32]
    trimmed = " ".join(words)
    max_chars = EMBEDDING_MAX_TOKENS * 3
    return trimmed[:max_chars] if len(trimmed) > max_chars else trimmed


def _embed_batch(client: httpx.Client, url: str, headers: dict, batch: list[str]) -> list[list[float]]:
    global _calls, _retries, _last_error, _last_status_code, _last_success_at
    payload = {"model": _model, "input": [_truncate_text(item) for item in batch]}
    for attempt in range(len(RETRY_DELAYS) + 1):
        _calls += 1
        try:
            response = client.post(url, headers=headers, json=payload)
            _last_status_code = response.status_code
            if response.status_code in (429, 503) and attempt < len(RETRY_DELAYS):
                _retries += 1
                time.sleep(RETRY_DELAYS[attempt])
                continue
            response.raise_for_status()
            body = response.json()
            rows = sorted(body["data"], key=lambda item: item["index"])
            vectors = [item["embedding"] for item in rows]
            if len(vectors) != len(batch):
                raise EmbeddingError("Embedding response count did not match batch size.")
            for vec in vectors:
                if not isinstance(vec, list) or len(vec) != EMBEDDING_DIMENSIONS:
                    raise EmbeddingError(
                        f"Unexpected embedding dimension; expected {EMBEDDING_DIMENSIONS}."
                    )
            _last_error = None
            _last_success_at = datetime.now(timezone.utc).isoformat()
            return vectors
        except httpx.HTTPStatusError as exc:
            _last_error = f"http_{exc.response.status_code}"
            raise EmbeddingError(f"Embedding API returned HTTP {exc.response.status_code}.") from exc
        except httpx.TimeoutException as exc:
            _last_error = "timeout"
            raise EmbeddingError("Embedding API request timed out.") from exc
        except httpx.RequestError as exc:
            _last_error = type(exc).__name__
            raise EmbeddingError(f"Embedding API connection failed: {type(exc).__name__}.") from exc
        except (KeyError, ValueError, TypeError) as exc:
            _last_error = type(exc).__name__
            raise EmbeddingError(f"Embedding response parse error: {type(exc).__name__}.") from exc
    raise EmbeddingError("Embedding API retry limit reached.")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts in bounded batches of up to 16 items using bge-small-en-v1.5."""
    if not texts:
        return []
    if not (_base_url and _api_key and _model):
        raise EmbeddingError("Embedding API requires EMBEDDING_BASE_URL, EMBEDDING_API_KEY and EMBEDDING_MODEL.")
    url = _embeddings_url()
    verify = _verify_certificate()
    headers = {
        "Authorization": f"Bearer {_api_key}",
        "Content-Type": "application/json",
    }
    vectors: list[list[float]] = []
    with httpx.Client(timeout=httpx.Timeout(EMBEDDING_TIMEOUT_SECONDS), verify=verify) as client:
        for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = texts[start : start + EMBEDDING_BATCH_SIZE]
            vectors.extend(_embed_batch(client, url, headers, batch))
    return vectors
