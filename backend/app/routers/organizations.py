"""Organizations router — CRUD, membership management, SSO config, audit log."""

import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.organization import OrganizationMembership, OrganizationRecord
from app.models.user import UserRecord
from app.services.audit_service import AuditService

router = APIRouter(prefix="/organizations", tags=["organizations"])

# ── Schemas ───────────────────────────────────────────────────────────────────


class OrgCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-z0-9-]+$")
    plan: str = Field(default="free")

    @field_validator("plan")
    @classmethod
    def _valid_plan(cls, v: str) -> str:
        if v not in {"free", "pro", "enterprise"}:
            raise ValueError("plan must be free, pro, or enterprise")
        return v


class OrgUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    plan: str | None = None

    @field_validator("plan")
    @classmethod
    def _valid_plan(cls, v: str | None) -> str | None:
        if v is not None and v not in {"free", "pro", "enterprise"}:
            raise ValueError("plan must be free, pro, or enterprise")
        return v


class OrgResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    is_active: bool
    created_at: datetime
    member_count: int = 0

    model_config = {"from_attributes": True}


class MembershipResponse(BaseModel):
    id: str
    organization_id: str
    user_id: str
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class InviteMemberRequest(BaseModel):
    user_id: str
    role: str = "member"

    @field_validator("role")
    @classmethod
    def _valid_role(cls, v: str) -> str:
        if v not in {"owner", "admin", "member"}:
            raise ValueError("role must be owner, admin, or member")
        return v


class SSOConfigRequest(BaseModel):
    """SAML 2.0 IdP settings stored in org.settings_json under 'sso' key."""

    idp_metadata_url: str | None = None
    idp_entity_id: str | None = None
    idp_sso_url: str | None = None
    idp_certificate: str | None = None  # Base64-encoded X.509 cert
    allowed_domains: list[str] = Field(default_factory=list)
    enforce_sso: bool = False  # If True, block password login for org users


class SSOConfigResponse(BaseModel):
    enabled: bool
    idp_entity_id: str | None
    idp_sso_url: str | None
    allowed_domains: list[str]
    enforce_sso: bool
    scim_token_hint: str | None = None  # last 6 chars of SCIM token for verification


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_org_or_404(db: Session, org_id: str) -> OrganizationRecord:
    org = (
        db.query(OrganizationRecord)
        .filter(
            OrganizationRecord.id == org_id,
            OrganizationRecord.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def _require_org_role(db: Session, org_id: str, user_id: str, *roles: str) -> OrganizationMembership:
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == user_id,
        )
        .first()
    )
    if not membership or membership.role not in roles:
        raise HTTPException(status_code=403, detail="Insufficient organization permissions")
    return membership


# ── CRUD ──────────────────────────────────────────────────────────────────────


@router.post("", status_code=201, response_model=OrgResponse)
def create_organization(
    body: OrgCreateRequest,
    request: Request,
    user=Depends(get_current_user),
):
    db = get_db()
    try:
        org = OrganizationRecord(
            id=str(uuid.uuid4()),
            name=body.name,
            slug=body.slug,
            plan=body.plan,
            settings_json={},
            metadata_json={},
        )
        db.add(org)
        db.flush()  # get org.id before committing

        # Creator becomes owner
        membership = OrganizationMembership(
            id=str(uuid.uuid4()),
            organization_id=org.id,
            user_id=user.id,
            role="owner",
        )
        db.add(membership)
        db.commit()
        db.refresh(org)

        AuditService.log(
            db,
            action="org.created",
            user_id=user.id,
            organization_id=org.id,
            actor=user.username,
            target_type="org",
            target_id=org.id,
            **AuditService.from_request(request),
        )
        count = db.query(OrganizationMembership).filter_by(organization_id=org.id).count()
        return OrgResponse(**org.__dict__, member_count=count)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Organization slug already taken")
    finally:
        db.close()


@router.get("", response_model=list[OrgResponse])
def list_my_organizations(user=Depends(get_current_user)):
    db = get_db()
    try:
        memberships = db.query(OrganizationMembership).filter_by(user_id=user.id).all()
        result = []
        for m in memberships:
            org = db.query(OrganizationRecord).filter_by(id=m.organization_id, is_active=True).first()
            if not org:
                continue
            count = db.query(OrganizationMembership).filter_by(organization_id=org.id).count()
            result.append(OrgResponse(**org.__dict__, member_count=count))
        return result
    finally:
        db.close()


@router.get("/{org_id}", response_model=OrgResponse)
def get_organization(org_id: str, user=Depends(get_current_user)):
    db = get_db()
    try:
        _require_org_role(db, org_id, user.id, "owner", "admin", "member")
        org = _get_org_or_404(db, org_id)
        count = db.query(OrganizationMembership).filter_by(organization_id=org.id).count()
        return OrgResponse(**org.__dict__, member_count=count)
    finally:
        db.close()


@router.patch("/{org_id}", response_model=OrgResponse)
def update_organization(
    org_id: str,
    body: OrgUpdateRequest,
    request: Request,
    user=Depends(get_current_user),
):
    db = get_db()
    try:
        _require_org_role(db, org_id, user.id, "owner", "admin")
        org = _get_org_or_404(db, org_id)
        if body.name is not None:
            org.name = body.name
        if body.plan is not None:
            org.plan = body.plan
        db.commit()
        db.refresh(org)
        AuditService.log(
            db,
            action="org.updated",
            user_id=user.id,
            organization_id=org.id,
            actor=user.username,
            target_type="org",
            target_id=org.id,
            **AuditService.from_request(request),
        )
        count = db.query(OrganizationMembership).filter_by(organization_id=org.id).count()
        return OrgResponse(**org.__dict__, member_count=count)
    finally:
        db.close()


@router.delete("/{org_id}", status_code=204)
def delete_organization(org_id: str, request: Request, user=Depends(get_current_user)):
    db = get_db()
    try:
        _require_org_role(db, org_id, user.id, "owner")
        org = _get_org_or_404(db, org_id)
        org.is_active = False
        db.commit()
        AuditService.log(
            db,
            action="org.deleted",
            user_id=user.id,
            organization_id=org_id,
            actor=user.username,
            **AuditService.from_request(request),
        )
    finally:
        db.close()


# ── Membership ────────────────────────────────────────────────────────────────


@router.get("/{org_id}/members", response_model=list[MembershipResponse])
def list_members(org_id: str, user=Depends(get_current_user)):
    db = get_db()
    try:
        _require_org_role(db, org_id, user.id, "owner", "admin", "member")
        return db.query(OrganizationMembership).filter_by(organization_id=org_id).all()
    finally:
        db.close()


@router.post("/{org_id}/members", status_code=201, response_model=MembershipResponse)
def invite_member(
    org_id: str,
    body: InviteMemberRequest,
    request: Request,
    user=Depends(get_current_user),
):
    db = get_db()
    try:
        _require_org_role(db, org_id, user.id, "owner", "admin")
        _get_org_or_404(db, org_id)
        target = db.query(UserRecord).filter_by(id=body.user_id, is_active=True).first()
        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        existing = db.query(OrganizationMembership).filter_by(organization_id=org_id, user_id=body.user_id).first()
        if existing:
            raise HTTPException(status_code=409, detail="User is already a member")

        m = OrganizationMembership(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            user_id=body.user_id,
            role=body.role,
        )
        db.add(m)
        db.commit()
        db.refresh(m)

        AuditService.log(
            db,
            action="org.member_added",
            user_id=user.id,
            organization_id=org_id,
            actor=user.username,
            target_type="user",
            target_id=body.user_id,
            **AuditService.from_request(request),
        )
        return m
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="User is already a member")
    finally:
        db.close()


@router.delete("/{org_id}/members/{user_id}", status_code=204)
def remove_member(
    org_id: str,
    user_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    db = get_db()
    try:
        # Owners/admins can remove others; members can remove themselves
        caller_m = _require_org_role(db, org_id, user.id, "owner", "admin", "member")
        if caller_m.role == "member" and user_id != user.id:
            raise HTTPException(status_code=403, detail="Members can only remove themselves")

        m = db.query(OrganizationMembership).filter_by(organization_id=org_id, user_id=user_id).first()
        if not m:
            raise HTTPException(status_code=404, detail="Member not found")

        db.delete(m)
        db.commit()
        AuditService.log(
            db,
            action="org.member_removed",
            user_id=user.id,
            organization_id=org_id,
            actor=user.username,
            target_type="user",
            target_id=user_id,
            **AuditService.from_request(request),
        )
    finally:
        db.close()


# ── SSO / SAML Config ─────────────────────────────────────────────────────────


@router.get("/{org_id}/sso", response_model=SSOConfigResponse)
def get_sso_config(org_id: str, user=Depends(get_current_user)):
    db = get_db()
    try:
        _require_org_role(db, org_id, user.id, "owner", "admin")
        org = _get_org_or_404(db, org_id)
        sso = (org.settings_json or {}).get("sso", {})
        scim_token: str = (org.settings_json or {}).get("scim_token", "")
        return SSOConfigResponse(
            enabled=bool(sso.get("idp_entity_id")),
            idp_entity_id=sso.get("idp_entity_id"),
            idp_sso_url=sso.get("idp_sso_url"),
            allowed_domains=sso.get("allowed_domains", []),
            enforce_sso=sso.get("enforce_sso", False),
            scim_token_hint=f"...{scim_token[-6:]}" if len(scim_token) >= 6 else None,
        )
    finally:
        db.close()


@router.put("/{org_id}/sso", response_model=SSOConfigResponse)
def configure_sso(
    org_id: str,
    body: SSOConfigRequest,
    request: Request,
    user=Depends(get_current_user),
):
    db = get_db()
    try:
        _require_org_role(db, org_id, user.id, "owner", "admin")
        org = _get_org_or_404(db, org_id)
        if org.plan not in ("pro", "enterprise"):
            raise HTTPException(
                status_code=402,
                detail="SSO requires a Pro or Enterprise plan",
            )
        settings = dict(org.settings_json or {})
        settings["sso"] = {
            "idp_metadata_url": body.idp_metadata_url,
            "idp_entity_id": body.idp_entity_id,
            "idp_sso_url": body.idp_sso_url,
            "idp_certificate": body.idp_certificate,
            "allowed_domains": body.allowed_domains,
            "enforce_sso": body.enforce_sso,
        }
        org.settings_json = settings
        db.commit()

        AuditService.log(
            db,
            action="org.sso_configured",
            user_id=user.id,
            organization_id=org.id,
            actor=user.username,
            target_type="org",
            target_id=org.id,
            detail={"idp_entity_id": body.idp_entity_id, "enforce_sso": body.enforce_sso},
            **AuditService.from_request(request),
        )
        scim_token: str = settings.get("scim_token", "")
        sso = settings["sso"]
        return SSOConfigResponse(
            enabled=bool(sso.get("idp_entity_id")),
            idp_entity_id=sso.get("idp_entity_id"),
            idp_sso_url=sso.get("idp_sso_url"),
            allowed_domains=sso.get("allowed_domains", []),
            enforce_sso=sso.get("enforce_sso", False),
            scim_token_hint=f"...{scim_token[-6:]}" if len(scim_token) >= 6 else None,
        )
    finally:
        db.close()


@router.post("/{org_id}/sso/scim-token", response_model=dict)
def rotate_scim_token(
    org_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    """Generate (or rotate) the SCIM bearer token for this org.  Returns the full token ONCE."""
    db = get_db()
    try:
        _require_org_role(db, org_id, user.id, "owner")
        org = _get_org_or_404(db, org_id)
        if org.plan not in ("pro", "enterprise"):
            raise HTTPException(status_code=402, detail="SCIM requires Pro or Enterprise plan")

        token = secrets.token_urlsafe(32)
        settings = dict(org.settings_json or {})
        settings["scim_token"] = token
        org.settings_json = settings
        db.commit()

        AuditService.log(
            db,
            action="org.scim_token_rotated",
            user_id=user.id,
            organization_id=org.id,
            actor=user.username,
            **AuditService.from_request(request),
        )
        return {"scim_token": token, "warning": "Store this token — it will not be shown again."}
    finally:
        db.close()


# ── Audit Log ─────────────────────────────────────────────────────────────────


@router.get("/{org_id}/audit-log")
def get_audit_log(
    org_id: str,
    limit: int = 50,
    offset: int = 0,
    action: str | None = None,
    user=Depends(get_current_user),
):
    db = get_db()
    try:
        _require_org_role(db, org_id, user.id, "owner", "admin")
        entries = AuditService.list(db, organization_id=org_id, action=action, limit=limit, offset=offset)
        return [
            {
                "id": e.id,
                "action": e.action,
                "actor": e.actor,
                "target_type": e.target_type,
                "target_id": e.target_id,
                "result": e.result,
                "ip_address": e.ip_address,
                "created_at": e.created_at,
            }
            for e in entries
        ]
    finally:
        db.close()
