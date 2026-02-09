"""Simple in-memory rate limiter middleware.

Uses a sliding-window approach per client IP to enforce requests-per-minute
limits.  Suitable for development and single-process deployments.  For
production behind a load balancer, swap this for a Redis-backed implementation.
"""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter keyed by client IP address.

    Parameters:
        app: The ASGI application to wrap.
        requests_per_minute: Maximum number of requests allowed per IP
            within a 60-second sliding window.
    """

    def __init__(self, app: ASGIApp, requests_per_minute: int = 60) -> None:
        super().__init__(app)
        self.rpm = requests_per_minute
        self.window_seconds = 60.0
        # client_ip -> list of request timestamps
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """Extract the client IP from the request.

        Respects ``X-Forwarded-For`` when present (reverse proxy setups),
        falling back to the direct connection IP.
        """
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Take the first (leftmost) IP from the chain.
            return forwarded.split(",")[0].strip()
        if request.client is not None:
            return request.client.host
        return "unknown"

    def _prune_window(self, client_ip: str, now: float) -> None:
        """Remove timestamps older than the sliding window."""
        cutoff = now - self.window_seconds
        timestamps = self._requests[client_ip]
        # Find the first index within the window using a linear scan.
        # For the expected request rates this is fast enough.
        idx = 0
        for idx, ts in enumerate(timestamps):
            if ts >= cutoff:
                break
        else:
            # All timestamps are expired.
            idx = len(timestamps)
        self._requests[client_ip] = timestamps[idx:]

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        """Check rate limit before forwarding the request."""
        # Skip rate limiting for health checks and WebSocket upgrades.
        if request.url.path in ("/health", "/") or request.headers.get("upgrade") == "websocket":
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        now = time.monotonic()

        self._prune_window(client_ip, now)
        timestamps = self._requests[client_ip]

        if len(timestamps) >= self.rpm:
            retry_after = int(self.window_seconds - (now - timestamps[0])) + 1
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"Rate limit of {self.rpm} requests per minute exceeded.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)

        response = await call_next(request)

        # Attach informational rate-limit headers.
        remaining = max(0, self.rpm - len(timestamps))
        response.headers["X-RateLimit-Limit"] = str(self.rpm)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
