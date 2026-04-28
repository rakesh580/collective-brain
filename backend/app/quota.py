"""Per-org quota gating for expensive endpoints (Week 18).

The W17 per-IP middleware in ``app/middleware/rate_limit.py`` already
absorbs the runaway-script case at the edge. This module sits one layer
deeper: it caps how much of the *expensive* surface area (LLM calls and
data ingestion) a single tenant can burn through, even if they spread
the load across many IPs or many users.

Two cost classes are defined:

* ``"llm"`` — anything that hits the LLM provider. One call costs ~100×
  a list-fetch in dollars and latency, so the budget is small and
  measured per minute.
* ``"standard"`` — heavy non-LLM endpoints (ingestion, batch reads).
  Budget is generous but bounded so a runaway pipeline cannot drown
  the worker pool.

Usage in a router::

    from app.quota import org_quota

    @router.post("/query")
    async def query_brain(
        body: QueryRequest,
        request: Request,
        user=Depends(get_current_user),
        _quota=Depends(org_quota("llm")),
    ):
        ...

The gate raises ``HTTPException(429)`` when the budget is exhausted and
sets ``X-Quota-*`` response headers on every successful pass-through so
clients can self-throttle.

Fail-open behaviour matches the W17 middleware: if Redis is missing or
explodes, requests pass through. Better to under-limit briefly than 500
every expensive call when the cache wobbles.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Literal

from fastapi import Depends, HTTPException, Request, Response, status

from app.dependencies import get_current_user

logger = logging.getLogger("collective_brain.quota")

CostClass = Literal["llm", "standard"]

# Redis key prefix for runtime quota overrides written by the admin
# `/admin/quotas/{org_id}/override` endpoint (W19). The value is a JSON
# document `{"limit": int, "expires_at": float}` and the TTL is set to
# match `expires_at - now()` so a stale key cannot outlive the human
# intent that put it there.
OVERRIDE_KEY_PREFIX = "quota:override"


def override_key(org_id: str, cost_class: str) -> str:
    """Stable key shape for override lookups. Used by both the gate and
    the admin endpoint so they cannot drift apart."""
    return f"{OVERRIDE_KEY_PREFIX}:{org_id}:{cost_class}"


def org_quota(cost_class: CostClass):
    """Build a FastAPI dependency that enforces a per-org quota.

    Returns a callable suitable for ``Depends(...)``. The dependency
    pulls the authenticated user via ``get_current_user``, derives the
    org id, and checks the appropriate budget against Redis.
    """

    async def _gate(
        request: Request,
        response: Response,
        user=Depends(get_current_user),
    ) -> None:
        settings = request.app.state.settings

        # Runtime override (mirrors W17 middleware) so the integration
        # test client doesn't burn through the budget across the suite.
        runtime_enabled = getattr(
            request.app.state,
            "quota_enabled",
            getattr(settings, "quota_enabled", True),
        )
        if not runtime_enabled:
            return

        org_id = _resolve_org_id(user)
        max_requests, window_seconds = _budget_for(settings, cost_class)

        # Admin override (W19) — if an active override exists in Redis,
        # use its limit instead of the configured baseline. Window is
        # not overridden because rolling windows narrower than 1s are
        # nonsensical, and ones wider than the baseline lose the
        # "burst protection" property of a sliding window.
        override_limit = await _read_override(request, org_id=org_id, cost_class=cost_class)
        if override_limit is not None:
            max_requests = override_limit

        key = f"org:{org_id}:{cost_class}"
        allowed, remaining = await _check(request, key=key, max_requests=max_requests, window_seconds=window_seconds)

        if not allowed:
            _record_metric(cost_class, "blocked")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": f"Per-org {cost_class} quota exceeded",
                    "cost_class": cost_class,
                    "limit": max_requests,
                    "window_seconds": window_seconds,
                },
                headers={
                    "X-Quota-Class": cost_class,
                    "X-Quota-Limit": str(max_requests),
                    "X-Quota-Remaining": "0",
                    "X-Quota-Reset": str(window_seconds),
                    "Retry-After": str(window_seconds),
                },
            )

        _record_metric(cost_class, "allowed")
        # Surface budget on successful responses so well-behaved clients
        # can pace themselves before they trip the 429.
        response.headers["X-Quota-Class"] = cost_class
        response.headers["X-Quota-Limit"] = str(max_requests)
        response.headers["X-Quota-Remaining"] = str(max(0, remaining))
        response.headers["X-Quota-Reset"] = str(window_seconds)

    return _gate


def _resolve_org_id(user) -> str:
    """Return a stable string key for the user's org.

    Users without an org (legacy single-tenant accounts) are bucketed
    under ``"_no_org"`` so they still share a budget rather than each
    getting infinite headroom under a unique key.
    """
    org_id = getattr(user, "organization_id", None)
    if not org_id:
        return "_no_org"
    return str(org_id)


def _budget_for(settings, cost_class: CostClass) -> tuple[int, int]:
    window = int(getattr(settings, "quota_window_seconds", 60) or 60)
    if cost_class == "llm":
        max_requests = int(getattr(settings, "quota_llm_per_window", 30) or 30)
    else:
        max_requests = int(getattr(settings, "quota_standard_per_window", 300) or 300)
    return max_requests, window


async def _read_override(request: Request, *, org_id: str, cost_class: str) -> int | None:
    """Look up a live quota override in Redis. Returns the override
    limit (an int) when one is active, or None when there is none.

    Fail-open posture: on any Redis error we return None so the gate
    falls back to the configured baseline. This matches the rest of
    this module — losing an override is strictly safer than failing
    the request because we couldn't read it.
    """
    redis = getattr(request.app.state, "redis", None)
    if redis is None or getattr(redis, "_redis", None) is None:
        return None
    try:
        raw = await redis._redis.get(override_key(org_id, cost_class))
    except Exception:
        logger.warning(
            "quota: override read failed for org=%s class=%s, falling back to baseline",
            org_id,
            cost_class,
            exc_info=True,
        )
        return None
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
        # Defensive expiry check — Redis TTL is the authoritative
        # boundary, but a clock-skew or a manually-written key could
        # leave a stale value behind. We re-check expires_at here to
        # be tolerant of either failure mode.
        expires_at = float(payload.get("expires_at", 0))
        if expires_at and expires_at <= time.time():
            return None
        return int(payload["limit"])
    except (ValueError, KeyError, TypeError):
        logger.warning(
            "quota: malformed override payload for org=%s class=%s — ignoring",
            org_id,
            cost_class,
        )
        return None


async def _check(request: Request, *, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
    """Wrap RedisService.check_rate_limit with the same fail-open
    posture used by the W17 middleware. A missing redis stub or any
    exception lets the request through and logs the miss."""
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        return True, max_requests
    try:
        return await redis.check_rate_limit(key, max_requests, window_seconds)
    except Exception:
        logger.warning("quota: redis check failed for key=%s, failing open", key, exc_info=True)
        return True, max_requests


def _record_metric(cost_class: str, outcome: str) -> None:
    """Increment ``cb_quota_decisions_total``. Failure swallowed —
    metrics outage must never break the request path."""
    try:
        from app.services.metrics import QUOTA_DECISIONS_TOTAL

        QUOTA_DECISIONS_TOTAL.labels(cost_class=cost_class, outcome=outcome).inc()
    except Exception:  # pragma: no cover — defensive
        logger.warning("quota: metric emission failed", exc_info=True)
