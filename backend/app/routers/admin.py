"""Admin-only maintenance endpoints.

Exposes:
- POST /admin/backfill-topics — re-canonicalize topics & expertise_tags.
- GET /admin/jobs — list registered scheduled jobs.
- POST /admin/trigger-job/{job_name} — manually run a registered job.
- GET /admin/alembic-version — current DB revision + expected head.
- POST /admin/apply-migrations — run ``alembic upgrade head`` from inside
  the container (works around the Supabase-IPv6 issue that prevents
  GitHub Actions runners from reaching the DB for migrations).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import text

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


def _alembic_current_revision(db) -> str | None:
    """Read the alembic_version table directly. None if the table is missing."""
    try:
        row = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
        return row[0] if row else None
    except Exception:  # table missing, etc.
        return None


def _alembic_head_revision() -> str | None:
    """Read the head revision from the local migrations dir without touching the DB."""
    try:
        import os

        from alembic.config import Config
        from alembic.script import ScriptDirectory

        ini_path = os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")
        alembic_cfg = Config()
        alembic_cfg.set_main_option("config_file_name", os.path.abspath(ini_path))
        alembic_cfg.set_main_option(
            "script_location",
            os.path.join(os.path.dirname(__file__), "..", "..", "alembic"),
        )
        script = ScriptDirectory.from_config(alembic_cfg)
        return script.get_current_head()
    except Exception as exc:  # pragma: no cover — migration packaging issue
        logger.warning("Could not read Alembic head revision: %s", exc)
        return None


@router.get("/alembic-version")
async def alembic_version(request: Request):
    """Report current DB revision vs. expected head. Helps diagnose missing
    migrations without hunting HF Spaces logs."""
    _require_admin(request)
    db = create_session()
    try:
        current = _alembic_current_revision(db)
    finally:
        db.close()
    head = _alembic_head_revision()
    return {
        "current": current,
        "head": head,
        "at_head": (current is not None and current == head),
    }


@router.post("/apply-migrations")
async def apply_migrations(request: Request):
    """Run ``alembic upgrade head`` from inside the container.

    Starred as the escape hatch for the Supabase-IPv6 issue: GitHub Actions
    runners can't reach Supabase Nano's IPv6-only DB, so the manual
    migrate.yml workflow fails. The running HF Space container DOES have a
    working DB connection (that's how the app serves requests), so running
    Alembic from here is reliable.
    """
    _require_admin(request)

    from app.config import get_settings
    from app.db.database import _run_alembic_migrations

    settings = get_settings()

    # Capture pre/post revision so the caller knows what changed.
    db = create_session()
    try:
        before = _alembic_current_revision(db)
    finally:
        db.close()

    error: str | None = None
    try:
        _run_alembic_migrations(settings)
    except Exception as exc:
        error = str(exc)
        logger.error("apply-migrations failed: %s", exc, exc_info=True)

    db = create_session()
    try:
        after = _alembic_current_revision(db)
    finally:
        db.close()

    head = _alembic_head_revision()

    return {
        "status": "ok" if error is None else "error",
        "before": before,
        "after": after,
        "head": head,
        "at_head": after is not None and after == head,
        "error": error,
    }
