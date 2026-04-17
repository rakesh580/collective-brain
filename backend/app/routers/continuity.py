"""Continuity router — API endpoints for knowledge continuity scoring."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.db.database import create_session
from app.dependencies import get_current_user
from app.services.continuity_service import ContinuityScoreService

router = APIRouter()

_service = ContinuityScoreService()


def _get_db():
    return create_session()


class ProjectContinuityRequest(BaseModel):
    artifact_ids: list[str]


@router.get("/dashboard")
async def get_continuity_dashboard(
    request: Request,
    user=Depends(get_current_user),
):
    """Get full continuity dashboard — overall score, at-risk members, gaps, recommendations."""
    db = _get_db()
    try:
        return _service.get_continuity_dashboard(db)
    finally:
        db.close()


@router.get("/member/{member_id}")
async def get_member_continuity(
    member_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    """Get continuity score for a specific member.

    Shows what would happen if this member leaves: knowledge at risk,
    backup members, and recommendations.
    """
    db = _get_db()
    try:
        result = _service.calculate_member_continuity(db, member_id)
        if result["member_name"] == "Unknown":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found",
            )
        return result
    finally:
        db.close()


@router.get("/team")
async def get_team_continuity(
    request: Request,
    user=Depends(get_current_user),
):
    """Get team-wide continuity analysis.

    Aggregates individual member scores, identifies weakest links and knowledge gaps.
    """
    db = _get_db()
    try:
        return _service.calculate_team_continuity(db)
    finally:
        db.close()


@router.post("/calculate")
async def trigger_continuity_calculation(
    request: Request,
    user=Depends(get_current_user),
):
    """Trigger full continuity recalculation and save scores to DB.

    Persists team-level and per-member continuity scores for trend tracking.
    """
    db = _get_db()
    try:
        return _service.save_continuity_snapshot(db)
    finally:
        db.close()


@router.post("/project")
async def get_project_continuity(
    body: ProjectContinuityRequest,
    request: Request,
    user=Depends(get_current_user),
):
    """Calculate continuity for a specific project (set of artifacts).

    Analyzes contributor distribution, active status, and single-point-of-failure risk.
    """
    db = _get_db()
    try:
        return _service.calculate_project_continuity(db, body.artifact_ids)
    finally:
        db.close()
