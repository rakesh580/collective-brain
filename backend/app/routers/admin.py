"""Admin-only maintenance endpoints.

Currently exposes:
- POST /admin/backfill-topics — re-canonicalize topics & expertise_tags
  against the current allowlist. Idempotent. Requires admin/owner role.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from app.db.database import create_session
from app.services.topic_backfill import run_topic_backfill

logger = logging.getLogger("collective_brain.routers.admin")
router = APIRouter()


def _require_admin(request: Request):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    if getattr(user, "role", "member") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


@router.post("/backfill-topics")
async def backfill_topics(
    request: Request,
    dry_run: bool = Query(default=False, description="Preview counts without writing"),
):
    """Recanonicalize every contribution's topics and rebuild members.expertise_tags."""
    _require_admin(request)
    db = create_session()
    try:
        result = run_topic_backfill(db, dry_run=dry_run)
    finally:
        db.close()

    # Invalidate graph cache so the new clean topics are reflected immediately
    if not dry_run and (result.contributions_changed or result.members_changed):
        try:
            from app.services.memory_graph import invalidate_graph_cache

            invalidate_graph_cache()
        except Exception as exc:  # pragma: no cover — cache is best-effort
            logger.warning("Failed to invalidate graph cache: %s", exc)

    return {"status": "ok", "dry_run": dry_run, **result.as_dict()}
