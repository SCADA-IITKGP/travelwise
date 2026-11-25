"""Latest published foreign-exchange reference rates with bounded fallback."""

import asyncio
import re
import time
from datetime import datetime, timezone

import httpx

PROVIDER = "Frankfurter"
PROVIDER_URL = "https://api.frankfurter.dev/v2/rate"
CACHE_TTL_SECONDS = 900
MAX_STALE_SECONDS = 86400
CIRCUIT_FAILURE_THRESHOLD = 3
CIRCUIT_RESET_SECONDS = 30

_cache: dict[tuple[str, str], dict] = {}
_lock = asyncio.Lock()
_failures = 0
_circuit_open_until = 0.0
_last_success: str | None = None
_last_error: str | None = None
_counters = {"requests": 0, "fresh_cache_hits": 0, "stale_fallbacks": 0, "provider_errors": 0}


class MarketDataUnavailable(RuntimeError):
    def __init__(self, message: str, *, retry_after_seconds: int = 30):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _valid_currency(value: str) -> str:
    code = value.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", code):
        raise ValueError("Currency codes must be three letters, such as INR or USD.")
    return code


def status() -> dict:
    now = time.monotonic()
    return {
        "provider": PROVIDER,
        "provider_url": "https://api.frankfurter.dev",
        "rate_type": "published reference rate; not a live market quote",
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "circuit_breaker": "open" if now < _circuit_open_until else "closed",
        "cache_entries": len(_cache),
        "last_success_at": _last_success,
        "last_error": _last_error,
        **_counters,
    }


def _with_freshness(entry: dict, freshness: str) -> dict:
    return {
        "base": entry["base"],
        "quote": entry["quote"],
        "rate": entry["rate"],
        "rate_date": entry["rate_date"],
        "provider": PROVIDER,
        "rate_type": "published reference rate; not a live market quote",
        "retrieved_at": entry["retrieved_at"],
        "freshness": freshness,
        "cache_age_seconds": max(0, int(time.monotonic() - entry["cached_monotonic"])),
    }


async def get_rate(base: str, quote: str) -> dict:
    global _failures, _circuit_open_until, _last_success, _last_error

    base, quote = _valid_currency(base), _valid_currency(quote)
    _counters["requests"] += 1
    if base == quote:
        return {
            "base": base, "quote": quote, "rate": 1.0,
            "rate_date": datetime.now(timezone.utc).date().isoformat(),
            "provider": "Identity conversion", "rate_type": "identity",
            "retrieved_at": _utc_now(), "freshness": "current", "cache_age_seconds": 0,
        }

    key = (base, quote)
    cached = _cache.get(key)
    now = time.monotonic()
    if cached and now - cached["cached_monotonic"] < CACHE_TTL_SECONDS:
        _counters["fresh_cache_hits"] += 1
        return _with_freshness(cached, "cached")

    async with _lock:
        cached = _cache.get(key)
        now = time.monotonic()
        if cached and now - cached["cached_monotonic"] < CACHE_TTL_SECONDS:
            _counters["fresh_cache_hits"] += 1
            return _with_freshness(cached, "cached")

        if now < _circuit_open_until:
            if cached and now - cached["cached_monotonic"] <= MAX_STALE_SECONDS:
                _counters["stale_fallbacks"] += 1
                return _with_freshness(cached, "stale_fallback")
            raise MarketDataUnavailable("Currency rate provider is temporarily unavailable.")

        last_exception: Exception | None = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(4.0, connect=2.0)) as client:
                    response = await client.get(f"{PROVIDER_URL}/{base}/{quote}")
                    response.raise_for_status()
                    payload = response.json()
                rate = float(payload["rate"])
                rate_date = payload["date"]
                if not rate > 0 or not isinstance(rate_date, str):
                    raise ValueError("Invalid rate payload")
                entry = {
                    "base": base,
                    "quote": quote,
                    "rate": rate,
                    "rate_date": rate_date,
                    "retrieved_at": _utc_now(),
                    "cached_monotonic": time.monotonic(),
                }
                _cache[key] = entry
                if len(_cache) > 200:
                    _cache.pop(next(iter(_cache)))
                _failures = 0
                _circuit_open_until = 0.0
                _last_success = entry["retrieved_at"]
                _last_error = None
                return _with_freshness(entry, "live")
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                last_exception = exc
                if attempt == 0:
                    await asyncio.sleep(0.2)

        _failures += 1
        _counters["provider_errors"] += 1
        _last_error = type(last_exception).__name__ if last_exception else "ProviderError"
        if _failures >= CIRCUIT_FAILURE_THRESHOLD:
            _circuit_open_until = time.monotonic() + CIRCUIT_RESET_SECONDS
        now = time.monotonic()
        if cached and now - cached["cached_monotonic"] <= MAX_STALE_SECONDS:
            _counters["stale_fallbacks"] += 1
            return _with_freshness(cached, "stale_fallback")
        raise MarketDataUnavailable(
            "Currency rate provider could not return a usable rate. No conversion was made."
        ) from last_exception
