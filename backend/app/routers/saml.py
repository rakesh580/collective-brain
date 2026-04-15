"""SAML 2.0 SSO router.

Endpoints:
  GET  /sso/saml/{org_slug}/metadata   — SP metadata XML (send to IdP)
  POST /sso/saml/{org_slug}/login      — Initiate SAML login (redirect to IdP)
  POST /sso/saml/{org_slug}/acs        — Assertion Consumer Service (IdP posts here)

The python3-saml library handles XML parsing, signature verification, and
assertion decryption.  We only need to wire it into FastAPI.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.database import create_session
from app.models.organization import OrganizationRecord
from app.models.user import UserRecord
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/sso/saml", tags=["sso"])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_saml_settings(org: OrganizationRecord, base_url: str) -> dict:
    """Build python3-saml settings dict from org.settings_json['sso']."""
    sso = (org.settings_json or {}).get("sso", {})
    sp_base = f"{base_url}/api/v1/sso/saml/{org.slug}"
    return {
        "strict": True,
        "debug": False,
        "sp": {
            "entityId": f"{sp_base}/metadata",
            "assertionConsumerService": {
                "url": f"{sp_base}/acs",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "x509cert": "",
            "privateKey": "",
        },
        "idp": {
            "entityId": sso.get("idp_entity_id", ""),
            "singleSignOnService": {
                "url": sso.get("idp_sso_url", ""),
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": sso.get("idp_certificate", ""),
        },
    }


def _get_org_by_slug(db: Session, slug: str) -> OrganizationRecord:
    org = db.query(OrganizationRecord).filter_by(slug=slug, is_active=True).first()
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")
    sso = (org.settings_json or {}).get("sso", {})
    if not sso.get("idp_entity_id"):
        raise HTTPException(status_code=400, detail="SSO is not configured for this organization")
    return org


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


# ── Metadata endpoint ─────────────────────────────────────────────────────────


@router.get("/{org_slug}/metadata", response_class=Response)
def sp_metadata(org_slug: str, request: Request):
    """Return SP metadata XML — give this URL to your IdP (Okta, Azure AD, etc.)."""
    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth  # noqa: F401
        from onelogin.saml2.settings import OneLogin_Saml2_Settings
    except ImportError:
        raise HTTPException(status_code=501, detail="python3-saml not installed")

    db = create_session()
    try:
        org = _get_org_by_slug(db, org_slug)
        settings_dict = _build_saml_settings(org, _base_url(request))
        saml_settings = OneLogin_Saml2_Settings(settings=settings_dict, sp_validation_only=True)
        metadata, errors = saml_settings.get_sp_metadata(), saml_settings.check_sp_settings()
        if errors:
            raise HTTPException(status_code=500, detail=f"SP settings error: {errors}")
        return Response(content=metadata, media_type="application/xml")
    finally:
        db.close()


# ── Login initiation ──────────────────────────────────────────────────────────


@router.get("/{org_slug}/login")
def saml_login(org_slug: str, request: Request):
    """Redirect the browser to the IdP's SSO URL with a SAML AuthnRequest."""
    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth
    except ImportError:
        raise HTTPException(status_code=501, detail="python3-saml not installed")

    db = create_session()
    try:
        org = _get_org_by_slug(db, org_slug)
        settings_dict = _build_saml_settings(org, _base_url(request))
        req = _prepare_saml_request(request)
        auth = OneLogin_Saml2_Auth(req, old_settings=settings_dict)
        redirect_url = auth.login()
        return RedirectResponse(url=redirect_url, status_code=302)
    finally:
        db.close()


# ── ACS (Assertion Consumer Service) ─────────────────────────────────────────


@router.post("/{org_slug}/acs", response_class=HTMLResponse)
async def saml_acs(
    org_slug: str,
    request: Request,
    SAMLResponse: str = Form(...),
    RelayState: str = Form(default=""),
):
    """Handle IdP POST-back with SAML assertion.

    On success: issue a JWT and redirect to the frontend with ?token=...
    On failure: return a 401 HTML page (browsers can't handle 401 JSON here).
    """
    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth
    except ImportError:
        raise HTTPException(status_code=501, detail="python3-saml not installed")

    db = create_session()
    try:
        org = _get_org_by_slug(db, org_slug)
        settings_dict = _build_saml_settings(org, _base_url(request))
        req = _prepare_saml_request(request, post_data={"SAMLResponse": SAMLResponse, "RelayState": RelayState})
        auth = OneLogin_Saml2_Auth(req, old_settings=settings_dict)
        auth.process_response()
        errors = auth.get_errors()

        if errors or not auth.is_authenticated():
            AuditService.log(
                db,
                action="auth.saml_login",
                result="fail",
                organization_id=org.id,
                detail={"errors": errors, "reason": auth.get_last_error_reason()},
                **AuditService.from_request(request),
            )
            return HTMLResponse(
                content=f"<h1>SSO Login Failed</h1><p>{auth.get_last_error_reason()}</p>",
                status_code=401,
            )

        nameid: str = auth.get_nameid()
        attributes: dict = auth.get_attributes()

        # Find or create the user by SAML NameID (email)
        user = db.query(UserRecord).filter((UserRecord.saml_nameid == nameid) | (UserRecord.email == nameid)).first()

        if not user:
            # Auto-provision a new user from SAML attributes
            display_name = _attr(attributes, "displayName", "givenName") or nameid.split("@")[0]
            username = _slugify_username(db, nameid.split("@")[0])
            user = UserRecord(
                id=str(uuid.uuid4()),
                username=username,
                email=nameid,
                display_name=display_name,
                auth_provider="saml",
                saml_nameid=nameid,
                saml_provider=org.settings_json.get("sso", {}).get("idp_entity_id"),
                organization_id=org.id,
                is_active=True,
                created_at=datetime.now(UTC),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        else:
            # Update SAML fields on existing user
            user.saml_nameid = nameid
            user.saml_provider = org.settings_json.get("sso", {}).get("idp_entity_id")
            if not user.organization_id:
                user.organization_id = org.id
            user.last_login = datetime.now(UTC)
            if user.auth_provider not in ("saml", "saml+local"):
                user.auth_provider = "saml+local" if user.password_hash else "saml"
            db.commit()

        settings = request.app.state.settings
        auth_svc = AuthService(settings)
        access_token = auth_svc.create_token(user.id)
        refresh_token = auth_svc.create_refresh_token(user.id)

        AuditService.log(
            db,
            action="auth.saml_login",
            user_id=user.id,
            organization_id=org.id,
            actor=user.username,
            result="ok",
            **AuditService.from_request(request),
        )

        # Redirect to frontend with tokens — validate RelayState to prevent open redirect
        from urllib.parse import urlparse

        frontend_url = RelayState or "/"
        parsed = urlparse(frontend_url)
        # Only allow relative URLs (no scheme/netloc) to prevent open redirect
        if parsed.scheme or parsed.netloc:
            frontend_url = "/"
        sep = "&" if "?" in frontend_url else "?"
        redirect_to = f"{frontend_url}{sep}token={access_token}&refresh_token={refresh_token}"
        return RedirectResponse(url=redirect_to, status_code=302)

    finally:
        db.close()


# ── Utilities ─────────────────────────────────────────────────────────────────


def _prepare_saml_request(request: Request, post_data: dict | None = None) -> dict:
    """Build the python3-saml request dict from a FastAPI Request."""
    url = str(request.url)
    https = url.startswith("https")
    return {
        "https": "on" if https else "off",
        "http_host": request.headers.get("host", "localhost"),
        "server_port": request.url.port or (443 if https else 80),
        "script_name": request.url.path,
        "get_data": dict(request.query_params),
        "post_data": post_data or {},
    }


def _attr(attributes: dict, *keys: str, default: str = "") -> str:
    for key in keys:
        values = attributes.get(key) or attributes.get(
            f"http://schemas.xmlsoap.org/ws/2005/05/identity/claims/{key.lower()}"
        )
        if values:
            return values[0] if isinstance(values, list) else values
    return default


def _slugify_username(db: Session, base: str) -> str:
    """Derive a unique username from the email local part."""
    import re

    slug = re.sub(r"[^a-z0-9_]", "_", base.lower())[:30]
    candidate = slug
    i = 1
    while db.query(UserRecord).filter_by(username=candidate).first():
        candidate = f"{slug}_{i}"
        i += 1
    return candidate
