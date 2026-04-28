"""Unit tests for the W19 quota override read path.

These tests target the new override-aware logic added on top of the
W18 gate. The W18 happy-path / blocked-path / fail-open coverage
lives in ``test_quota_gate.py`` and is unchanged.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from fastapi import Depends, FastAPI
from starlette.testclient import TestClient

from app.dependencies import get_current_user
from app.quota import org_quota, override_key


class _FakeInnerRedis:
    """Minimal aioredis surface our override-read path uses."""

    def __init__(self, kv: dict[str, str], *, raise_on_get: bool = False) -> None:
        self._kv = kv
        self.raise_on_get = raise_on_get

    async def get(self, key: str):
        if self.raise_on_get:
            raise RuntimeError("redis unreachable")
        return self._kv.get(key)


class _FakeRedisService:
    """Stand-in for ``RedisService`` exposing both ``check_rate_limit``
    (used by the W18 gate) and ``_redis`` (used by the W19 override
    read). The gate's policy is configurable per test."""

    def __init__(
        self,
        policy: Callable[[str, int, int], tuple[bool, int]],
        kv: dict[str, str] | None = None,
        *,
        raise_on_get: bool = False,
    ) -> None:
        self.policy = policy
        self.calls: list[tuple[str, int, int]] = []
        self._redis = _FakeInnerRedis(kv or {}, raise_on_get=raise_on_get)

    async def check_rate_limit(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        self.calls.append((key, max_requests, window_seconds))
        return self.policy(key, max_requests, window_seconds)


def _settings(*, llm: int = 5, standard: int = 10, window: int = 60) -> SimpleNamespace:
    return SimpleNamespace(
        quota_llm_per_window=llm,
        quota_standard_per_window=standard,
        quota_window_seconds=window,
        quota_enabled=True,
    )


def _build_app(redis: Any, *, cost_class: str = "llm", org_id: str = "org-A") -> FastAPI:
    app = FastAPI()
    app.state.redis = redis
    app.state.settings = _settings()
    fake_user = SimpleNamespace(id="u1", organization_id=org_id)
    app.dependency_overrides[get_current_user] = lambda: fake_user

    @app.post("/expensive")
    async def expensive(_quota=Depends(org_quota(cost_class))) -> dict[str, int]:
        return {"ok": 1}

    return app


def test_override_lifts_baseline_limit_when_active():
    """An active override is used as ``max_requests`` for the gate's
    sliding-window check, not the configured baseline. Verified by
    inspecting the policy's recorded ``(key, max_requests, window)``."""
    expires_at = time.time() + 60
    payload = json.dumps({"limit": 999, "expires_at": expires_at, "reason": "demo"})
    redis = _FakeRedisService(
        lambda key, mx, win: (True, mx - 1),
        kv={override_key("org-A", "llm"): payload},
    )
    app = _build_app(redis, cost_class="llm")
    with TestClient(app) as client:
        resp = client.post("/expensive")
    assert resp.status_code == 200
    # The recorded call uses the override's 999, not the configured 5.
    assert redis.calls[-1] == ("org:org-A:llm", 999, 60)


def test_expired_override_falls_back_to_baseline():
    """A key with ``expires_at`` already in the past is treated as
    absent. Belt-and-suspenders: the Redis TTL is the authoritative
    expiry, but a manually-written or clock-skewed key must not
    keep an effective override alive past its declared lifetime."""
    expires_at = time.time() - 1  # already expired
    payload = json.dumps({"limit": 999, "expires_at": expires_at})
    redis = _FakeRedisService(
        lambda key, mx, win: (True, mx - 1),
        kv={override_key("org-A", "llm"): payload},
    )
    app = _build_app(redis, cost_class="llm")
    with TestClient(app) as client:
        client.post("/expensive")
    assert redis.calls[-1] == ("org:org-A:llm", 5, 60)  # baseline llm=5


def test_no_override_uses_baseline():
    redis = _FakeRedisService(
        lambda key, mx, win: (True, mx - 1),
        kv={},  # no override key
    )
    app = _build_app(redis, cost_class="standard")
    with TestClient(app) as client:
        client.post("/expensive")
    assert redis.calls[-1] == ("org:org-A:standard", 10, 60)  # baseline standard=10


def test_malformed_override_json_is_ignored():
    """A corrupted override payload must not 500 the request — the
    gate logs and falls back to the baseline so customers don't see
    operational errors leak into their request path."""
    redis = _FakeRedisService(
        lambda key, mx, win: (True, mx - 1),
        kv={override_key("org-A", "llm"): "not-json{"},
    )
    app = _build_app(redis, cost_class="llm")
    with TestClient(app) as client:
        resp = client.post("/expensive")
    assert resp.status_code == 200
    assert redis.calls[-1] == ("org:org-A:llm", 5, 60)


def test_override_payload_missing_limit_is_ignored():
    """``KeyError`` on the limit field is caught and treated as a
    malformed override — falls back to baseline."""
    redis = _FakeRedisService(
        lambda key, mx, win: (True, mx - 1),
        kv={override_key("org-A", "llm"): json.dumps({"expires_at": time.time() + 60})},
    )
    app = _build_app(redis, cost_class="llm")
    with TestClient(app) as client:
        client.post("/expensive")
    assert redis.calls[-1] == ("org:org-A:llm", 5, 60)


def test_redis_exception_on_override_read_falls_open_to_baseline():
    """A Redis hiccup while reading the override must not block the
    request. Same fail-open posture as the rest of ``app/quota.py``."""
    redis = _FakeRedisService(
        lambda key, mx, win: (True, mx - 1),
        kv={},
        raise_on_get=True,
    )
    app = _build_app(redis, cost_class="llm")
    with TestClient(app) as client:
        resp = client.post("/expensive")
    assert resp.status_code == 200
    assert redis.calls[-1] == ("org:org-A:llm", 5, 60)


def test_override_only_applies_to_matching_cost_class():
    """An override on `llm` must NOT raise the budget for `standard`."""
    payload = json.dumps({"limit": 999, "expires_at": time.time() + 60})
    redis = _FakeRedisService(
        lambda key, mx, win: (True, mx - 1),
        kv={override_key("org-A", "llm"): payload},  # only llm has override
    )
    app = _build_app(redis, cost_class="standard")
    with TestClient(app) as client:
        client.post("/expensive")
    assert redis.calls[-1] == ("org:org-A:standard", 10, 60)


def test_override_keyspace_is_per_org():
    """An override on `org-X` must NOT leak into `org-A`'s budget."""
    payload = json.dumps({"limit": 999, "expires_at": time.time() + 60})
    redis = _FakeRedisService(
        lambda key, mx, win: (True, mx - 1),
        kv={override_key("org-X", "llm"): payload},
    )
    app = _build_app(redis, cost_class="llm", org_id="org-A")
    with TestClient(app) as client:
        client.post("/expensive")
    assert redis.calls[-1] == ("org:org-A:llm", 5, 60)
