"""Unit tests for the per-org quota gate (Week 18).

Strategy mirrors ``test_rate_limit_middleware.py``: build a tiny FastAPI
app, stub a fake redis on ``app.state.redis``, override the
``get_current_user`` dep to return a synthetic user with a known
``organization_id``, and drive scenarios through Starlette's TestClient.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import Depends, FastAPI
from starlette.testclient import TestClient

from app.dependencies import get_current_user
from app.quota import org_quota


class _FakeRedis:
    """Stand-in for ``RedisService.check_rate_limit``. ``policy`` is the
    function that decides ``(allowed, remaining)`` per call; tests inject
    one. Every call is recorded so we can assert the key shape."""

    def __init__(self, policy: Callable[[str, int, int], tuple[bool, int]]) -> None:
        self.policy = policy
        self.calls: list[tuple[str, int, int]] = []

    async def check_rate_limit(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        self.calls.append((key, max_requests, window_seconds))
        return self.policy(key, max_requests, window_seconds)


def _settings(
    *,
    llm: int = 5,
    standard: int = 10,
    window: int = 60,
    enabled: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        quota_llm_per_window=llm,
        quota_standard_per_window=standard,
        quota_window_seconds=window,
        quota_enabled=enabled,
    )


def _build_app(
    *,
    redis: Any = None,
    settings: SimpleNamespace | None = None,
    user: Any = None,
    cost_class: str = "llm",
    runtime_quota_enabled: bool | None = None,
) -> FastAPI:
    app = FastAPI()
    app.state.redis = redis
    app.state.settings = settings or _settings()
    if runtime_quota_enabled is not None:
        app.state.quota_enabled = runtime_quota_enabled

    fake_user = user or SimpleNamespace(id="u1", organization_id="org-A")
    app.dependency_overrides[get_current_user] = lambda: fake_user

    @app.post("/expensive")
    async def expensive(_quota=Depends(org_quota(cost_class))) -> dict[str, str]:
        return {"ok": "yes"}

    return app


def test_allows_request_under_budget_and_emits_quota_headers():
    """Allowed call surfaces the X-Quota-* triplet so clients can pace
    themselves before they trip the 429."""
    redis = _FakeRedis(lambda key, max_, win: (True, 4))
    app = _build_app(redis=redis, cost_class="llm")

    with TestClient(app) as client:
        resp = client.post("/expensive")

    assert resp.status_code == 200
    assert resp.headers["X-Quota-Class"] == "llm"
    assert resp.headers["X-Quota-Limit"] == "5"
    assert resp.headers["X-Quota-Remaining"] == "4"
    assert resp.headers["X-Quota-Reset"] == "60"


def test_blocks_request_over_budget_with_429_and_retry_after():
    """Over-budget request returns a clean 429 with a structured detail
    body and a Retry-After header so clients know when to back off."""
    redis = _FakeRedis(lambda key, max_, win: (False, 0))
    app = _build_app(redis=redis, cost_class="standard")

    with TestClient(app) as client:
        resp = client.post("/expensive")

    assert resp.status_code == 429
    assert resp.headers["X-Quota-Class"] == "standard"
    assert resp.headers["X-Quota-Remaining"] == "0"
    assert resp.headers["Retry-After"] == "60"
    detail = resp.json()["detail"]
    assert detail["cost_class"] == "standard"
    assert detail["limit"] == 10


def test_uses_per_org_per_class_key():
    """Key shape must be ``org:{id}:{cost_class}`` so different orgs and
    different classes get independent budgets."""
    redis = _FakeRedis(lambda key, max_, win: (True, 1))
    app = _build_app(redis=redis, cost_class="llm")

    with TestClient(app) as client:
        client.post("/expensive")

    assert redis.calls
    key, max_requests, window = redis.calls[0]
    assert key == "org:org-A:llm"
    assert max_requests == 5  # _settings(llm=5)
    assert window == 60


def test_separate_orgs_get_separate_budgets():
    """Two requests as different orgs must produce two distinct redis
    keys, not share one bucket."""
    redis = _FakeRedis(lambda key, max_, win: (True, 1))

    # Org A
    app_a = _build_app(
        redis=redis,
        user=SimpleNamespace(id="u1", organization_id="org-A"),
        cost_class="llm",
    )
    with TestClient(app_a) as client:
        client.post("/expensive")

    # Org B — fresh app, same redis stub so we can inspect call history
    app_b = _build_app(
        redis=redis,
        user=SimpleNamespace(id="u2", organization_id="org-B"),
        cost_class="llm",
    )
    with TestClient(app_b) as client:
        client.post("/expensive")

    keys = [c[0] for c in redis.calls]
    assert "org:org-A:llm" in keys
    assert "org:org-B:llm" in keys


def test_separate_classes_get_separate_budgets():
    """An LLM call and an ingestion call from the same org should hit
    two different keys — that's the whole point of cost classes."""
    redis = _FakeRedis(lambda key, max_, win: (True, 1))

    app_llm = _build_app(redis=redis, cost_class="llm")
    with TestClient(app_llm) as client:
        client.post("/expensive")

    app_std = _build_app(redis=redis, cost_class="standard")
    with TestClient(app_std) as client:
        client.post("/expensive")

    keys = [c[0] for c in redis.calls]
    assert "org:org-A:llm" in keys
    assert "org:org-A:standard" in keys


def test_user_with_no_org_falls_back_to_shared_bucket():
    """Legacy single-tenant users with organization_id=None must still
    be limited — they share a ``_no_org`` bucket so they can't burn
    infinite budget under unique unkeyed requests."""
    redis = _FakeRedis(lambda key, max_, win: (True, 1))
    app = _build_app(
        redis=redis,
        user=SimpleNamespace(id="u1", organization_id=None),
        cost_class="llm",
    )
    with TestClient(app) as client:
        client.post("/expensive")

    assert redis.calls[0][0] == "org:_no_org:llm"


def test_disabled_settings_flag_passes_everything_through():
    """``quota_enabled=False`` is the production kill switch. Even a
    redis decision of 'block' must be ignored, AND no redis call is
    made at all."""
    redis = _FakeRedis(lambda key, max_, win: (False, 0))  # would block
    app = _build_app(redis=redis, settings=_settings(enabled=False))

    with TestClient(app) as client:
        resp = client.post("/expensive")

    assert resp.status_code == 200
    assert "X-Quota-Limit" not in resp.headers
    assert redis.calls == []


def test_runtime_state_override_wins_over_settings_flag():
    """Integration tests flip ``app.state.quota_enabled = False`` so a
    long-lived TestClient hitting the same org many times doesn't burn
    through the budget across the suite. The dep must honor that even
    when settings.quota_enabled is True."""
    redis = _FakeRedis(lambda key, max_, win: (False, 0))  # would block
    app = _build_app(
        redis=redis,
        settings=_settings(enabled=True),
        runtime_quota_enabled=False,
    )

    with TestClient(app) as client:
        for _ in range(3):
            resp = client.post("/expensive")
            assert resp.status_code == 200

    assert redis.calls == [], "quota gate must be skipped when state flag is False"


def test_no_redis_on_app_state_fails_open():
    """During early lifespan or in tests without a redis stub, the gate
    must fail OPEN — better to let the request through than to 429
    every expensive call before Redis is ready."""
    app = _build_app(redis=None)

    with TestClient(app) as client:
        resp = client.post("/expensive")

    assert resp.status_code == 200
    # Headers should still be set so well-behaved clients can self-pace
    # using whatever budget the gate would have enforced.
    assert resp.headers["X-Quota-Limit"] == "5"


def test_redis_exception_fails_open():
    """If Redis raises (timeout, connection drop, etc.) we must NOT
    propagate the error to the user. Fail open with a logged warning."""

    class _BoomRedis:
        async def check_rate_limit(self, *args, **kwargs):
            raise RuntimeError("redis exploded")

    app = _build_app(redis=_BoomRedis())

    with TestClient(app) as client:
        resp = client.post("/expensive")

    assert resp.status_code == 200


def test_metric_emitted_for_allowed_and_blocked():
    """Each decision increments cb_quota_decisions_total exactly once
    with the right outcome label."""
    from app.services.metrics import QUOTA_DECISIONS_TOTAL

    def _value(cost_class: str, outcome: str) -> float:
        total = 0.0
        for metric in QUOTA_DECISIONS_TOTAL.collect():
            for sample in metric.samples:
                if (
                    sample.name.endswith("_total")
                    and sample.labels.get("cost_class") == cost_class
                    and sample.labels.get("outcome") == outcome
                ):
                    total += sample.value
        return total

    allowed_before = _value("llm", "allowed")
    blocked_before = _value("standard", "blocked")

    # One allowed LLM call.
    app_ok = _build_app(redis=_FakeRedis(lambda key, max_, win: (True, 5)), cost_class="llm")
    with TestClient(app_ok) as client:
        client.post("/expensive")

    # One blocked standard call.
    app_block = _build_app(redis=_FakeRedis(lambda key, max_, win: (False, 0)), cost_class="standard")
    with TestClient(app_block) as client:
        client.post("/expensive")

    assert _value("llm", "allowed") == pytest.approx(allowed_before + 1.0)
    assert _value("standard", "blocked") == pytest.approx(blocked_before + 1.0)


def test_window_value_propagates_from_settings_to_redis_call():
    """The settings ``quota_window_seconds`` must reach the redis call —
    otherwise ops can't tune the window in prod without a code change."""
    redis = _FakeRedis(lambda key, max_, win: (True, 1))
    app = _build_app(redis=redis, settings=_settings(window=30, llm=2))

    with TestClient(app) as client:
        client.post("/expensive")

    assert redis.calls[0][2] == 30
    assert redis.calls[0][1] == 2
