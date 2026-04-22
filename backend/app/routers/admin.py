"""Admin-only maintenance endpoints.

Exposes:
- POST /admin/backfill-topics — re-canonicalize topics & expertise_tags.
- GET /admin/jobs — list registered scheduled jobs.
- POST /admin/trigger-job/{job_name} — manually run a registered job.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from app.db.database import create_session
from app.services.scheduler import run_to_dict
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


@router.get("/jobs")
async def list_jobs(request: Request):
    """List every scheduled job with its last-run summary."""
    _require_admin(request)
    scheduler = request.app.state.scheduler
    return {"jobs": scheduler.list_jobs()}


@router.post("/trigger-job/{job_name}")
async def trigger_job(request: Request, job_name: str):
    """Manually run a registered job. Blocks until completion."""
    _require_admin(request)
    scheduler = request.app.state.scheduler
    try:
        run = await scheduler.run_now(job_name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown job '{job_name}'") from None
    return {"status": "ok", "run": run_to_dict(run)}
