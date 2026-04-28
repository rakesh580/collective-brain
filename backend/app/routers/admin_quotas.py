"""Admin quota dashboard + override endpoints (Week 19).

Operationalises the W18 per-org gate:

* ``GET /api/v1/admin/quotas`` — current usage per (org, cost_class).
  Reads ZCARD against the same sliding-window keys the gate writes to,
  so the dashboard cannot drift from enforcement.

* ``POST /api/v1/admin/quotas/{org_id}/override`` — temporarily lift the
  budget for one tenant during an incident. Stored in Redis with a TTL
  bounded by ``duration_minutes`` so a stale override cannot outlive
  the human intent.

* ``DELETE /api/v1/admin/quotas/{org_id}/override`` — revoke before
  expiry.

Auth: admin / owner role only, mirroring the rest of ``admin.py``.

Why Redis-only state (no DB rows): an override is an emergency lever
with a 15-minute-to-4-hour life. Persisting through restarts is
unnecessary; a Pod restart wipes the override and the customer goes
back to the baseline budget — exactly the "fail safe" outcome we want.
The audit trail lives in structured logs + the Prometheus gauge.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.db.database import create_session
from app.models.organization import OrganizationRecord
from app.quota import OVERRIDE_KEY_PREFIX, override_key

logger = logging.getLogger("collective_brain.routers.admin_quotas")
router = APIRouter()

CostClass = Literal["llm", "standard"]
COST_CLASSES: tuple[CostClass, ...] = ("llm", "standard")

# Hard ceiling on override duration. Without this an admin could set
# duration=99999, walk away, and the override would silently outlast
# the incident. 4 hours covers every realistic incident window we've
# seen; longer requests should re-trigger the override after triage.
MAX_OVERRIDE_MINUTES = 240


def _require_admin(request: Request):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    if getattr(user, "role", "member") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


class OverrideRequest(BaseModel):
    cost_class: CostClass
    new_limit: int = Field(..., gt=0, description="New per-window limit while the override is active")
    duration_minutes: int = Field(
        ...,
        gt=0,
        le=MAX_OVERRIDE_MINUTES,
        description=f"How long the override should last (max {MAX_OVERRIDE_MINUTES} minutes)",
    )
    reason: str | None = Field(
        default=None,
        max_length=240,
        description="Free-form note logged with the override for audit",
    )


def _baseline_for(settings, cost_class: CostClass) -> tuple[int, int]:
    window = int(getattr(settings, "quota_window_seconds", 60) or 60)
    if cost_class == "llm":
        max_requests = int(getattr(settings, "quota_llm_per_window", 30) or 30)
    else:
        max_requests = int(getattr(settings, "quota_standard_per_window", 300) or 300)
    return max_requests, window


async def _used_for(redis, org_id: str, cost_class: CostClass) -> int:
    """ZCARD on the sliding-window key the gate writes to.

    Returns 0 on any Redis hiccup — visualising "no usage" during a
    cache wobble is preferable to surfacing a 500 in the admin UI.
    """
    if redis is None or getattr(redis, "_redis", None) is None:
        return 0
    try:
        # Match the prefix used by RedisService.check_rate_limit (`rate:`).
        return int(await redis._redis.zcard(f"rate:org:{org_id}:{cost_class}"))
    except Exception:
        logger.warning(
            "admin_quotas: ZCARD failed for org=%s class=%s — reporting 0",
            org_id,
            cost_class,
            exc_info=True,
        )
        return 0


async def _override_for(redis, org_id: str, cost_class: CostClass) -> dict | None:
    if redis is None or getattr(redis, "_redis", None) is None:
        return None
    try:
        raw = await redis._redis.get(override_key(org_id, cost_class))
    except Exception:
        return None
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
        expires_at = float(payload.get("expires_at", 0))
        if expires_at and expires_at <= time.time():
            return None
        return {
            "limit": int(payload["limit"]),
            "expires_at": expires_at,
            "remaining_seconds": max(0, int(expires_at - time.time())),
            "reason": payload.get("reason"),
        }
    except (ValueError, KeyError, TypeError):
        return None


def _refresh_override_gauge(active_counts: dict[str, int]) -> None:
    """Set ``cb_quota_overrides_active`` to the current live override
    counts per cost class. Called from the dashboard endpoint so the
    gauge converges to ground truth even if an override expired
    silently between writes."""
    try:
        from app.services.metrics import QUOTA_OVERRIDES_ACTIVE

        for cost_class in COST_CLASSES:
            QUOTA_OVERRIDES_ACTIVE.labels(cost_class=cost_class).set(active_counts.get(cost_class, 0))
    except Exception:  # pragma: no cover — metrics outage must never break a request
        logger.warning("admin_quotas: gauge refresh failed", exc_info=True)


@router.get("/quotas")
async def list_quotas(request: Request) -> dict:
    """Return current usage and override state per (org, cost_class).

    Includes the synthetic ``_no_org`` bucket so legacy single-tenant
    accounts are visible alongside real orgs.
    """
    _require_admin(request)
    settings = request.app.state.settings
    redis = getattr(request.app.state, "redis", None)

    db = create_session()
    try:
        orgs = db.query(OrganizationRecord).all()
        org_descriptors = [{"id": o.id, "name": o.name, "slug": o.slug} for o in orgs]
    finally:
        db.close()

    # `_no_org` mirrors `app/quota.py:_resolve_org_id` so the dashboard
    # cannot lose visibility on legacy users with NULL organization_id.
    org_descriptors.append({"id": "_no_org", "name": "(legacy / single-tenant)", "slug": None})

    rows: list[dict] = []
    active_counts: dict[str, int] = {"llm": 0, "standard": 0}
    for org in org_descriptors:
        for cost_class in COST_CLASSES:
            baseline, window = _baseline_for(settings, cost_class)
            used = await _used_for(redis, org["id"], cost_class)
            override = await _override_for(redis, org["id"], cost_class)
            limit = override["limit"] if override else baseline
            if override:
                active_counts[cost_class] += 1
            rows.append(
                {
                    "org_id": org["id"],
                    "org_name": org["name"],
                    "org_slug": org["slug"],
                    "cost_class": cost_class,
                    "baseline_limit": baseline,
                    "effective_limit": limit,
                    "used": used,
                    "remaining": max(0, limit - used),
                    "window_seconds": window,
                    "override": override,
                }
            )

    _refresh_override_gauge(active_counts)
    return {"rows": rows, "generated_at": time.time(), "max_override_minutes": MAX_OVERRIDE_MINUTES}


@router.post("/quotas/{org_id}/override", status_code=201)
async def create_override(org_id: str, body: OverrideRequest, request: Request) -> dict:
    """Set a quota override for ``(org_id, cost_class)`` for N minutes.

    The TTL on the Redis key is set to match ``duration_minutes`` so
    an override never outlives the admin's stated intent — even if
    the gauge or the dashboard never refreshes.
    """
    user = _require_admin(request)
    redis = getattr(request.app.state, "redis", None)
    if redis is None or getattr(redis, "_redis", None) is None:
        raise HTTPException(status_code=503, detail="Redis unavailable — overrides cannot be applied")

    expires_at = time.time() + body.duration_minutes * 60
    payload = {
        "limit": body.new_limit,
        "expires_at": expires_at,
        "reason": body.reason,
        "set_by": getattr(user, "username", None) or getattr(user, "id", "unknown"),
        "set_at": time.time(),
    }
    ttl_seconds = body.duration_minutes * 60
    try:
        await redis._redis.set(
            override_key(org_id, body.cost_class),
            json.dumps(payload),
            ex=ttl_seconds,
        )
    except Exception:
        logger.exception("admin_quotas: failed to write override for org=%s", org_id)
        raise HTTPException(status_code=502, detail="Failed to write override to Redis") from None

    logger.info(
        "quota.override.set org=%s class=%s new_limit=%d duration_minutes=%d set_by=%s reason=%r",
        org_id,
        body.cost_class,
        body.new_limit,
        body.duration_minutes,
        payload["set_by"],
        body.reason,
    )

    try:
        from app.services.metrics import QUOTA_OVERRIDES_ACTIVE

        QUOTA_OVERRIDES_ACTIVE.labels(cost_class=body.cost_class).inc()
    except Exception:  # pragma: no cover
        pass

    return {
        "status": "ok",
        "org_id": org_id,
        "cost_class": body.cost_class,
        "limit": body.new_limit,
        "expires_at": expires_at,
        "remaining_seconds": ttl_seconds,
    }


@router.delete("/quotas/{org_id}/override")
async def clear_override(org_id: str, cost_class: CostClass, request: Request) -> dict:
    """Revoke an override before its TTL expires."""
    user = _require_admin(request)
    redis = getattr(request.app.state, "redis", None)
    if redis is None or getattr(redis, "_redis", None) is None:
        raise HTTPException(status_code=503, detail="Redis unavailable")

    try:
        deleted = await redis._redis.delete(override_key(org_id, cost_class))
    except Exception:
        logger.exception("admin_quotas: failed to delete override for org=%s", org_id)
        raise HTTPException(status_code=502, detail="Failed to revoke override") from None

    logger.info(
        "quota.override.cleared org=%s class=%s by=%s deleted=%d",
        org_id,
        cost_class,
        getattr(user, "username", "unknown"),
        deleted,
    )

    try:
        from app.services.metrics import QUOTA_OVERRIDES_ACTIVE

        if deleted:
            QUOTA_OVERRIDES_ACTIVE.labels(cost_class=cost_class).dec()
    except Exception:  # pragma: no cover
        pass

    return {"status": "ok", "deleted": bool(deleted)}


__all__ = ["router", "OVERRIDE_KEY_PREFIX"]
