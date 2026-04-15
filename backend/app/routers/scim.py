"""SCIM 2.0 Users resource.

RFC 7644 endpoints for IdP-driven user provisioning (Okta, Azure AD, etc.).
Auth: Bearer token stored in org.settings_json['scim_token'] (set via
      POST /api/v1/organizations/{id}/sso/scim-token).

Implemented endpoints:
  GET    /scim/v2/Users               — list users
  POST   /scim/v2/Users               — provision a new user
  GET    /scim/v2/Users/{user_id}     — get a user
  PUT    /scim/v2/Users/{user_id}     — full replace a user
  PATCH  /scim/v2/Users/{user_id}     — partial update (activate/deactivate)
  DELETE /scim/v2/Users/{user_id}     — deprovision a user

The X-SCIM-Org header (or a separate URL prefix per org) carries the org slug.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.database import create_session
from app.models.organization import OrganizationRecord
from app.models.user import UserRecord
from app.services.audit_service import AuditService

router = APIRouter(prefix="/scim/v2", tags=["scim"])

SCIM_CONTENT_TYPE = "application/scim+json"


# ── SCIM auth ─────────────────────────────────────────────────────────────────


def _authenticate_scim(authorization: str | None, db: Session) -> OrganizationRecord:
    """Validate the SCIM bearer token and return the corresponding organization."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="SCIM bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    # Scan all active orgs for matching token (tokens are short, table is small)
    orgs = db.query(OrganizationRecord).filter_by(is_active=True).all()
    for org in orgs:
        import hmac

        stored = (org.settings_json or {}).get("scim_token", "")
        if stored and hmac.compare_digest(stored, token):
            return org
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid SCIM token",
    )


# ── SCIM response helpers ─────────────────────────────────────────────────────


def _scim_user(user: UserRecord, request: Request) -> dict:
    base = str(request.base_url).rstrip("/")
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id": user.id,
        "externalId": user.scim_external_id,
        "userName": user.email,
        "name": {
            "formatted": user.display_name or user.username,
        },
        "emails": [{"value": user.email, "primary": True}],
        "active": user.is_active,
        "meta": {
            "resourceType": "User",
            "location": f"{base}/api/v1/scim/v2/Users/{user.id}",
            "created": user.created_at.isoformat() if user.created_at else None,
        },
    }


def _scim_error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
            "status": str(status_code),
            "detail": detail,
        },
        media_type=SCIM_CONTENT_TYPE,
    )


def _get_user_or_404(db: Session, user_id: str, org_id: str) -> UserRecord:
    user = db.query(UserRecord).filter_by(id=user_id, organization_id=org_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _slugify_username(db: Session, base: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9_]", "_", base.lower())[:30]
    candidate = slug
    i = 1
    while db.query(UserRecord).filter_by(username=candidate).first():
        candidate = f"{slug}_{i}"
        i += 1
    return candidate


# ── List Users ────────────────────────────────────────────────────────────────


@router.get("/Users")
def list_users(
    request: Request,
    startIndex: int = 1,
    count: int = 100,
    filter: str | None = None,
    authorization: str | None = Header(default=None),
):
    db = create_session()
    try:
        org = _authenticate_scim(authorization, db)
        q = db.query(UserRecord).filter_by(organization_id=org.id)

        # Basic SCIM filter: userName eq "email@example.com"
        if filter and 'userName eq "' in filter:
            email = filter.split('"')[1]
            q = q.filter(UserRecord.email == email)

        total = q.count()
        users = q.offset(startIndex - 1).limit(count).all()
        resources = [_scim_user(u, request) for u in users]

        return JSONResponse(
            content={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
                "totalResults": total,
                "startIndex": startIndex,
                "itemsPerPage": len(resources),
                "Resources": resources,
            },
            media_type=SCIM_CONTENT_TYPE,
        )
    finally:
        db.close()


# ── Get User ──────────────────────────────────────────────────────────────────


@router.get("/Users/{user_id}")
def get_user(
    user_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    db = create_session()
    try:
        org = _authenticate_scim(authorization, db)
        user = _get_user_or_404(db, user_id, org.id)
        return JSONResponse(content=_scim_user(user, request), media_type=SCIM_CONTENT_TYPE)
    finally:
        db.close()


# ── Provision User ────────────────────────────────────────────────────────────


@router.post("/Users", status_code=201)
async def provision_user(
    request: Request,
    authorization: str | None = Header(default=None),
):
    body: dict = await request.json()
    db = create_session()
    try:
        org = _authenticate_scim(authorization, db)

        # Extract core attributes
        email = body.get("userName") or ""
        if not email:
            return _scim_error(400, "userName (email) is required")

        external_id = body.get("externalId")
        active = body.get("active", True)
        name = body.get("name", {})
        display_name = name.get("formatted") or name.get("givenName", "")

        # Idempotency: return existing user if already provisioned
        existing = (
            db.query(UserRecord)
            .filter((UserRecord.scim_external_id == external_id) if external_id else (UserRecord.email == email))
            .filter_by(organization_id=org.id)
            .first()
        )

        if existing:
            # Update and return
            existing.display_name = display_name or existing.display_name
            existing.is_active = active
            if external_id:
                existing.scim_external_id = external_id
            db.commit()
            db.refresh(existing)
            AuditService.log(
                db,
                action="scim.user_updated",
                organization_id=org.id,
                actor="scim",
                target_type="user",
                target_id=existing.id,
                detail={"email": email, "active": active},
            )
            return JSONResponse(
                content=_scim_user(existing, request),
                status_code=200,
                media_type=SCIM_CONTENT_TYPE,
            )

        username = _slugify_username(db, email.split("@")[0])
        user = UserRecord(
            id=str(uuid.uuid4()),
            username=username,
            email=email,
            display_name=display_name or username,
            scim_external_id=external_id,
            auth_provider="scim",
            organization_id=org.id,
            is_active=active,
            created_at=datetime.now(UTC),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        AuditService.log(
            db,
            action="scim.user_provisioned",
            organization_id=org.id,
            actor="scim",
            target_type="user",
            target_id=user.id,
            detail={"email": email},
        )
        return JSONResponse(
            content=_scim_user(user, request),
            status_code=201,
            media_type=SCIM_CONTENT_TYPE,
        )
    finally:
        db.close()


# ── Full Replace (PUT) ────────────────────────────────────────────────────────


@router.put("/Users/{user_id}")
async def replace_user(
    user_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    body: dict = await request.json()
    db = create_session()
    try:
        org = _authenticate_scim(authorization, db)
        user = _get_user_or_404(db, user_id, org.id)

        name = body.get("name", {})
        user.display_name = name.get("formatted") or name.get("givenName") or user.display_name
        user.is_active = body.get("active", user.is_active)
        if body.get("externalId"):
            user.scim_external_id = body["externalId"]

        db.commit()
        db.refresh(user)
        AuditService.log(
            db,
            action="scim.user_updated",
            organization_id=org.id,
            actor="scim",
            target_type="user",
            target_id=user.id,
        )
        return JSONResponse(content=_scim_user(user, request), media_type=SCIM_CONTENT_TYPE)
    finally:
        db.close()


# ── Partial Update (PATCH) ────────────────────────────────────────────────────


@router.patch("/Users/{user_id}")
async def patch_user(
    user_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    """Handles SCIM PATCH operations — primarily used to activate/deactivate users."""
    body: dict = await request.json()
    db = create_session()
    try:
        org = _authenticate_scim(authorization, db)
        user = _get_user_or_404(db, user_id, org.id)

        for op in body.get("Operations", []):
            op_type = op.get("op", "").lower()
            path = op.get("path", "")
            value = op.get("value")

            if op_type == "replace":
                if path == "active":
                    user.is_active = bool(value)
                elif path == "name.formatted" and value:
                    user.display_name = value
                elif isinstance(value, dict):
                    # Handle replace with no path: value is a dict of attributes
                    if "active" in value:
                        user.is_active = bool(value["active"])
                    if "name" in value:
                        n = value["name"]
                        user.display_name = n.get("formatted") or n.get("givenName") or user.display_name

        db.commit()
        db.refresh(user)

        action = "scim.user_deprovisioned" if not user.is_active else "scim.user_updated"
        AuditService.log(
            db,
            action=action,
            organization_id=org.id,
            actor="scim",
            target_type="user",
            target_id=user.id,
        )
        return JSONResponse(content=_scim_user(user, request), media_type=SCIM_CONTENT_TYPE)
    finally:
        db.close()


# ── Delete (Deprovision) ──────────────────────────────────────────────────────


@router.delete("/Users/{user_id}", status_code=204)
def deprovision_user(
    user_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    db = create_session()
    try:
        org = _authenticate_scim(authorization, db)
        user = _get_user_or_404(db, user_id, org.id)
        # Soft-delete: deactivate rather than delete to preserve audit trail
        user.is_active = False
        db.commit()
        AuditService.log(
            db,
            action="scim.user_deprovisioned",
            organization_id=org.id,
            actor="scim",
            target_type="user",
            target_id=user_id,
            detail={"email": user.email},
        )
    finally:
        db.close()
