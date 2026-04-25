"""Unit tests for the per-IP rate-limit middleware.

Strategy: build a tiny FastAPI app with the middleware mounted, stub a
fake redis on ``app.state.redis``, and use Starlette's TestClient to
fire requests. The fake redis lets us drive allow/block decisions
deterministically without running a real Redis or relying on time."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.middleware.rate_limit import RateLimitMiddleware


class _FakeRedis:
    """Stand-in for ``RedisService``. ``policy`` is the function that
    decides ``(allowed, remaining)`` per call; tests inject one."""

    def __init__(self, policy: Callable[[str, int, int], tuple[bool, int]]) -> None:
        self.policy = policy
        self.calls: list[tuple[str, int, int]] = []

    async def check_rate_limit(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        self.calls.append((key, max_requests, window_seconds))
        return self.policy(key, max_requests, window_seconds)


def _build_app(
    *,
    redis: Any = None,
    max_requests: int = 3,
    window_seconds: int = 60,
    enabled: bool = True,
) -> FastAPI:
    app = FastAPI()
    app.state.redis = redis
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=max_requests,
        window_seconds=window_seconds,
        enabled=enabled,
    )

    @app.get("/api/v1/ping")
    def ping() -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics")
    def metrics() -> str:
        return "metrics"

    @app.post("/api/v1/slack/events")
    def slack_events() -> dict[str, str]:
        return {"ok": "yes"}

    @app.post("/api/v1/github/webhooks")
    def github_webhooks() -> dict[str, str]:
        return {"ok": "yes"}

    return app


def test_allows_request_under_limit_and_emits_headers():
    """First request through. Redis says allowed, response should carry
    the X-RateLimit-* triplet so well-behaved clients can self-throttle."""
    redis = _FakeRedis(lambda key, max_, win: (True, 2))
    app = _build_app(redis=redis, max_requests=3, window_seconds=60)

    with TestClient(app) as client:
        resp = client.get("/api/v1/ping")

    assert resp.status_code == 200
    assert resp.headers["X-RateLimit-Limit"] == "3"
    assert resp.headers["X-RateLimit-Remaining"] == "2"
    assert resp.headers["X-RateLimit-Reset"] == "60"
    assert redis.calls and redis.calls[0][0].startswith("ip:")


def test_blocks_request_over_limit_with_proper_headers_and_body():
    """Redis says blocked. Middleware must produce a clean 429 with
    Retry-After and JSON body explaining the limit."""
    redis = _FakeRedis(lambda key, max_, win: (False, 0))
    app = _build_app(redis=redis, max_requests=3, window_seconds=60)

    with TestClient(app) as client:
        resp = client.get("/api/v1/ping")

    assert resp.status_code == 429
    assert resp.headers["X-RateLimit-Remaining"] == "0"
    assert resp.headers["Retry-After"] == "60"
    body = resp.json()
    assert body["detail"] == "Too many requests"
    assert body["limit"] == 3
    assert body["window_seconds"] == 60


def test_health_endpoint_bypasses_limiter():
    """Liveness probes must never be 429ed — the orchestrator would
    treat them as unhealthy and restart the container."""
    redis = _FakeRedis(lambda key, max_, win: (False, 0))  # would block
    app = _build_app(redis=redis, max_requests=1)

    with TestClient(app) as client:
        for _ in range(5):
            resp = client.get("/api/v1/health")
            assert resp.status_code == 200

    # The Redis stub was never even consulted — bypass short-circuits.
    assert redis.calls == []


def test_metrics_endpoint_bypasses_limiter():
    """Prometheus scrape target must never be throttled, otherwise we
    lose visibility exactly when traffic is high."""
    redis = _FakeRedis(lambda key, max_, win: (False, 0))
    app = _build_app(redis=redis)

    with TestClient(app) as client:
        for _ in range(5):
            resp = client.get("/metrics")
            assert resp.status_code == 200

    assert redis.calls == []


def test_webhook_endpoints_bypass_limiter():
    """Slack and GitHub retry on 429, which would cause duplicate
    processing of the same delivery. Both webhook prefixes must skip
    the limiter — no exceptions."""
    redis = _FakeRedis(lambda key, max_, win: (False, 0))
    app = _build_app(redis=redis)

    with TestClient(app) as client:
        slack = client.post("/api/v1/slack/events")
        github = client.post("/api/v1/github/webhooks")

    assert slack.status_code == 200
    assert github.status_code == 200
    assert redis.calls == []


def test_disabled_kill_switch_passes_everything_through():
    """``rate_limit_enabled=False`` is the production kill switch.
    Even a Redis decision of 'block' must be ignored."""
    redis = _FakeRedis(lambda key, max_, win: (False, 0))
    app = _build_app(redis=redis, enabled=False)

    with TestClient(app) as client:
        resp = client.get("/api/v1/ping")

    assert resp.status_code == 200
    # Headers are NOT set when the limiter is disabled — they'd be
    # misleading (claiming a budget that isn't enforced).
    assert "X-RateLimit-Limit" not in resp.headers
    assert redis.calls == []


def test_runtime_state_override_wins_over_construct_time_flag():
    """Integration tests flip ``app.state.rate_limit_enabled = False``
    so a session-scoped TestClient (one host) doesn't burn through the
    budget across tests. The middleware must honor that runtime flag
    even when constructed with enabled=True."""
    redis = _FakeRedis(lambda key, max_, win: (False, 0))  # would block
    app = _build_app(redis=redis, max_requests=1, enabled=True)
    app.state.rate_limit_enabled = False  # runtime kill — what tests do

    with TestClient(app) as client:
        for _ in range(5):
            resp = client.get("/api/v1/ping")
            assert resp.status_code == 200

    assert redis.calls == [], "limiter must be skipped when state flag is False"


def test_no_redis_on_app_state_fails_open():
    """During early lifespan or in unit-test apps, ``app.state.redis``
    may be missing entirely. The limiter must fail OPEN — better to let
    the request through than to 429 every call before Redis is ready."""
    app = _build_app(redis=None, max_requests=1)

    with TestClient(app) as client:
        # Five requests with max_requests=1 — every one should pass.
        for _ in range(5):
            resp = client.get("/api/v1/ping")
            assert resp.status_code == 200


def test_redis_exception_fails_open():
    """If Redis raises (timeout, connection drop, etc.) we must NOT
    propagate the error to the user. Fail open with a logged warning;
    better to under-limit briefly than to 500 the whole API."""

    class _BoomRedis:
        async def check_rate_limit(self, *args, **kwargs):
            raise RuntimeError("redis exploded")

    app = _build_app(redis=_BoomRedis(), max_requests=1)

    with TestClient(app) as client:
        resp = client.get("/api/v1/ping")

    assert resp.status_code == 200


def test_uses_per_ip_key():
    """Rate-limit key must include the caller IP so two different
    clients can't share a budget. The fake redis records every key it
    sees — assert the prefix is right."""
    redis = _FakeRedis(lambda key, max_, win: (True, 3))
    app = _build_app(redis=redis)

    with TestClient(app) as client:
        client.get("/api/v1/ping")

    assert redis.calls
    key = redis.calls[0][0]
    assert key.startswith("ip:")
    # TestClient defaults to "testclient" as host
    assert key != "ip:"


def test_metric_emitted_for_allowed_and_blocked():
    """Each decision increments cb_rate_limit_hits_total exactly once
    with the right outcome label."""
    from app.services.metrics import RATE_LIMIT_HITS_TOTAL

    # Snapshot the counters BEFORE the test so concurrent test runs in
    # the same process don't make this test flaky.
    def _value(outcome: str) -> float:
        # Sum across all path labels for the given outcome.
        total = 0.0
        for metric in RATE_LIMIT_HITS_TOTAL.collect():
            for sample in metric.samples:
                if sample.name.endswith("_total") and sample.labels.get("outcome") == outcome:
                    total += sample.value
        return total

    allowed_before = _value("allowed")
    blocked_before = _value("blocked")

    # One allowed call.
    redis_ok = _FakeRedis(lambda key, max_, win: (True, 5))
    app_ok = _build_app(redis=redis_ok)
    with TestClient(app_ok) as client:
        client.get("/api/v1/ping")

    # One blocked call.
    redis_block = _FakeRedis(lambda key, max_, win: (False, 0))
    app_block = _build_app(redis=redis_block)
    with TestClient(app_block) as client:
        client.get("/api/v1/ping")

    assert _value("allowed") == pytest.approx(allowed_before + 1.0)
    assert _value("blocked") == pytest.approx(blocked_before + 1.0)
