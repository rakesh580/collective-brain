"""Org X-Ray router — organizational analysis and team comparison."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.db.database import create_session
from app.dependencies import get_current_user

router = APIRouter()


def _get_db():
    return create_session()


class CompareTeamsRequest(BaseModel):
    team_a_member_ids: list[str]
    team_b_member_ids: list[str]


@router.get("/report")
async def get_org_xray_report(
    user=Depends(get_current_user),
):
    """Generate full org X-ray report."""
    from app.services.org_xray_service import OrgXrayService

    svc = OrgXrayService()
    db = _get_db()
    try:
        return svc.generate_org_xray(db)
    finally:
        db.close()


@router.post("/compare-teams")
async def compare_teams(
    body: CompareTeamsRequest,
    user=Depends(get_current_user),
):
    """Compare two teams (M&A analysis)."""
    from app.services.org_xray_service import OrgXrayService

    svc = OrgXrayService()
    db = _get_db()
    try:
        return svc.compare_teams(
            db=db,
            team_a_member_ids=body.team_a_member_ids,
            team_b_member_ids=body.team_b_member_ids,
        )
    finally:
        db.close()
