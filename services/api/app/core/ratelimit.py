"""In-process fixed-window rate limiter (per client IP).

Adequate for a single API instance. A multi-instance deployment should move this to the
edge (CDN/WAF) or a shared store; documented in docs/deployment.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

EXEMPT_PREFIXES = ("/api/v1/health",)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, limit_per_minute: int) -> None:
        super().__init__(app)
        self.limit = limit_per_minute
        self._windows: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
        self._lock = Lock()

    def _client_key(self, request: Request) -> str:
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self.limit <= 0 or request.url.path.startswith(EXEMPT_PREFIXES):
            return await call_next(request)
        key = self._client_key(request)
        window = int(time.time() // 60)
        with self._lock:
            start, count = self._windows[key]
            if start != window:
                start, count = window, 0
            count += 1
            self._windows[key] = (start, count)
            if len(self._windows) > 10_000:  # bound memory
                self._windows = defaultdict(
                    lambda: (0, 0), {k: v for k, v in self._windows.items() if v[0] == window}
                )
        remaining = max(self.limit - count, 0)
        if count > self.limit:
            retry = 60 - int(time.time() % 60)
            return JSONResponse(
                {
                    "error": {
                        "code": "rate_limited",
                        "message": "Too many requests",
                        "details": None,
                    }
                },
                status_code=429,
                headers={"Retry-After": str(retry), "X-RateLimit-Limit": str(self.limit)},
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
