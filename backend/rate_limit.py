"""Small process-local API guard for a single-instance demo deployment."""

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 120
_requests: dict[str, deque[float]] = defaultdict(deque)
_blocked = 0


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        global _blocked
        if request.url.path == "/health":
            return await call_next(request)

        now = time.monotonic()
        client = request.client.host if request.client else "unknown"
        bucket = _requests[client]
        while bucket and now - bucket[0] >= WINDOW_SECONDS:
            bucket.popleft()

        if len(bucket) >= MAX_REQUESTS_PER_WINDOW:
            _blocked += 1
            retry_after = max(1, int(WINDOW_SECONDS - (now - bucket[0])))
            return JSONResponse(
                status_code=429,
                content={"detail": "Request limit reached. Retry after the indicated delay.", "failure_category": "rate_limit"},
                headers={"Retry-After": str(retry_after), "X-RateLimit-Limit": str(MAX_REQUESTS_PER_WINDOW)},
            )

        bucket.append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(MAX_REQUESTS_PER_WINDOW)
        response.headers["X-RateLimit-Remaining"] = str(max(0, MAX_REQUESTS_PER_WINDOW - len(bucket)))
        if len(_requests) > 10000:
            cutoff = now - WINDOW_SECONDS
            for address in list(_requests):
                if not _requests[address] or _requests[address][-1] < cutoff:
                    del _requests[address]
        return response


def status() -> dict:
    return {"scope": "single API process", "limit": MAX_REQUESTS_PER_WINDOW,
            "window_seconds": WINDOW_SECONDS, "blocked_requests": _blocked,
            "active_clients": len(_requests)}
