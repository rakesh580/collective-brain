"""Offboarding router — generate/retrieve risk reports, transition member status."""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.db.database import create_session
from app.models.member import MemberRecord
from app.models.offboarding_report import OffboardingReport
from app.services.offboarding_service import OffboardingService

logger = logging.getLogger("collective_brain.routers.offboarding")
router = APIRouter()
_svc = OffboardingService()


def _require_admin(request: Request):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    if getattr(user, "role", "member") not in ("admin", "owner"):
        from fastapi import HTTPException as _H

        raise _H(status_code=403, detail="Admin role required for offboarding operations")
    return user


# ── Response schemas ───────────────────────────────────────────────────────────


class TransferRecommendation(BaseModel):
    topic: str
    recommended_member_id: str
    recommended_member_name: str


class OffboardingReportResponse(BaseModel):
    id: str
    member_id: str
    created_at: str
    risk_level: str | None
    unique_expertise: list[str]
    sole_contributor_artifact_ids: list[str]
    transfer_recommendations: list[TransferRecommendation]
    summary: str | None

    @classmethod
    def from_record(cls, r: OffboardingReport) -> "OffboardingReportResponse":
        recs = [TransferRecommendation(**rec) for rec in (r.transfer_recommendations or [])]
        return cls(
            id=r.id,
            member_id=r.member_id,
            created_at=r.created_at.isoformat() if r.created_at else "",
            risk_level=r.risk_level,
            unique_expertise=r.unique_expertise or [],
            sole_contributor_artifact_ids=r.sole_contributor_artifact_ids or [],
            transfer_recommendations=recs,
            summary=r.summary,
        )


class MemberStatusResponse(BaseModel):
    id: str
    name: str
    status: str | None


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post(
    "/members/{member_id}/offboard",
    response_model=OffboardingReportResponse,
    summary="Generate an offboarding risk report for a member",
)
def offboard_member(member_id: str, request: Request):
    """Compute and persist an offboarding report, then mark the member as offboarding."""
    current_user = _require_admin(request)
    db = create_session()
    try:
        llm = getattr(request.app.state, "llm_service", None)
        report = _svc.generate_report(db, member_id=member_id, created_by=current_user.id, llm_service=llm)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    finally:
        db.close()
    return OffboardingReportResponse.from_record(report)


@router.get(
    "/members/{member_id}/offboarding-report",
    response_model=OffboardingReportResponse,
    summary="Retrieve the latest offboarding report for a member",
)
def get_offboarding_report(member_id: str, request: Request):
    _require_admin(request)
    db = create_session()
    try:
        report = _svc.get_report(db, member_id=member_id)
    finally:
        db.close()
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No offboarding report found for this member. Call POST /members/{id}/offboard first.",
        )
    return OffboardingReportResponse.from_record(report)


@router.post(
    "/members/{member_id}/offboard/complete",
    response_model=MemberStatusResponse,
    summary="Mark a member as fully offboarded",
)
def complete_offboarding(member_id: str, request: Request):
    _require_admin(request)
    db = create_session()
    try:
        member = _svc.complete_offboarding(db, member_id=member_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    finally:
        db.close()
    return MemberStatusResponse(id=member.id, name=member.name, status=member.status)


@router.get(
    "/members/{member_id}/status",
    response_model=MemberStatusResponse,
    summary="Get member lifecycle status",
)
def get_member_status(member_id: str, request: Request):
    _require_admin(request)
    db = create_session()
    try:
        member = db.query(MemberRecord).filter(MemberRecord.id == member_id).first()
    finally:
        db.close()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return MemberStatusResponse(id=member.id, name=member.name, status=member.status)
