"""Per-IP rate-limit middleware.

Sliding-window limiter that runs in front of every ``/api/v1/*`` request
(plus the SPA fallback). Uses ``RedisService.check_rate_limit`` (already
ZSET-pipelined with an in-memory fallback) so this middleware adds no
new infrastructure.

Bypass paths:
- ``/api/v1/health`` — liveness probes must never be throttled
- ``/metrics`` — Prometheus scrape target must never be throttled
- Webhook routes (``/api/v1/slack/events``, ``/api/v1/github/webhooks``) —
  Slack/GitHub retry on 429, which would cause duplicate processing

Response headers on every request that goes through the limiter:
- ``X-RateLimit-Limit`` — the configured budget
- ``X-RateLimit-Remaining`` — count left in this window
- ``X-RateLimit-Reset`` — seconds until the window resets (approximate)

On block (429), additionally:
- ``Retry-After`` — same value as Reset

Week 17 of the ultra plan (Q2 abuse-protection quarter).
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("collective_brain.rate_limit")

# Path bypasses are matched as exact strings AND prefix matches. Webhook
# prefixes need prefix-match because GitHub sends to
# /api/v1/github/webhooks and Slack to /api/v1/slack/events with possible
# path suffixes added by their SDKs.
_BYPASS_EXACT: frozenset[str] = frozenset(
    {
        "/api/v1/health",
        "/health",  # legacy mount
        "/metrics",
    }
)

_BYPASS_PREFIXES: tuple[str, ...] = (
    "/api/v1/slack/events",
    "/api/v1/github/webhooks",
)


def _should_bypass(path: str) -> bool:
    if path in _BYPASS_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in _BYPASS_PREFIXES)


def _client_ip(request: Request) -> str:
    """Best-effort caller IP. Falls back to ``"unknown"`` so the limiter
    keys are bounded even when ``request.client`` is None (some Starlette
    test clients don't populate it)."""
    client = getattr(request, "client", None)
    host = getattr(client, "host", None)
    return host or "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP global rate limit. Read settings off ``request.app.state.settings``
    so a single middleware instance serves both prod and tests."""

    def __init__(
        self,
        app,
        *,
        max_requests: int,
        window_seconds: int,
        enabled: bool = True,
    ) -> None:
        super().__init__(app)
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._enabled = enabled

    async def dispatch(self, request: Request, call_next) -> Response:
        # ``request.app.state.rate_limit_enabled`` overrides the
        # construct-time flag at runtime — tests flip this to False so a
        # session-scoped TestClient (one host = "testclient") doesn't trip
        # the limiter after 60 requests. Production never sets this attr,
        # falling back to ``self._enabled`` from settings.
        runtime_enabled = getattr(request.app.state, "rate_limit_enabled", self._enabled)
        if not runtime_enabled or _should_bypass(request.url.path):
            return await call_next(request)

        redis = getattr(request.app.state, "redis", None)
        ip = _client_ip(request)
        key = f"ip:{ip}"
        path_template = _path_template_for_metric(request)

        allowed, remaining = await _check(
            redis,
            key=key,
            max_requests=self._max_requests,
            window_seconds=self._window_seconds,
        )

        if not allowed:
            _record_metric(path_template, "blocked")
            return _build_429(self._max_requests, self._window_seconds)

        _record_metric(path_template, "allowed")
        response = await call_next(request)
        # Surface budget on every successful response so well-behaved
        # clients can self-throttle before they trip the 429.
        response.headers["X-RateLimit-Limit"] = str(self._max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(self._window_seconds)
        return response


async def _check(redis, *, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
    """Wrapper around RedisService.check_rate_limit. When Redis is missing
    entirely (early lifespan / unit tests without a redis stub) the limiter
    fails OPEN — better to let the request through than to 429 every call
    on startup. The dedicated in-memory fallback inside RedisService kicks
    in when the connection is configured but the network is down."""
    if redis is None:
        return True, max_requests
    try:
        return await redis.check_rate_limit(key, max_requests, window_seconds)
    except Exception:
        logger.warning("rate_limit: redis check failed, failing open", exc_info=True)
        return True, max_requests


def _path_template_for_metric(request: Request) -> str:
    """Return the matched route template (e.g. ``/api/v1/members/{id}``)
    for use as a Prometheus label. Falls back to the raw path if the
    router didn't bind one — this still avoids unbounded query-string
    cardinality because we use ``request.url.path``, not the full URL."""
    route = getattr(request.scope.get("route"), "path", None) if request.scope else None
    return route or request.url.path


def _record_metric(path: str, outcome: str) -> None:
    """Increment ``cb_rate_limit_hits_total``. Failure swallowed —
    metrics outage must never break the request path."""
    try:
        from app.services.metrics import RATE_LIMIT_HITS_TOTAL

        RATE_LIMIT_HITS_TOTAL.labels(path=path, outcome=outcome).inc()
    except Exception:  # pragma: no cover — defensive
        logger.warning("rate_limit: metric emission failed", exc_info=True)


def _build_429(max_requests: int, window_seconds: int) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests",
            "limit": max_requests,
            "window_seconds": window_seconds,
        },
        headers={
            "X-RateLimit-Limit": str(max_requests),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(window_seconds),
            "Retry-After": str(window_seconds),
        },
    )
