import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.requests import (
    RegisterRequest,
    LoginRequest,
    ProfileUpdateRequest,
    GoogleAuthRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.schemas.responses import UserResponse, AuthResponse
from app.services.auth_service import AuthService
from app.models.user import UserRecord
from app.db.database import get_session

logger = logging.getLogger(__name__)


async def _rate_limit(request: Request, key: str, max_requests: int, window: int = 60):
    """Check rate limit via Redis (or in-memory fallback). Raises 429 if exceeded."""
    redis = getattr(request.app.state, "redis", None)
    if not redis:
        return
    client_ip = request.client.host if request.client else "unknown"
    allowed, remaining = await redis.check_rate_limit(
        f"{key}:{client_ip}", max_requests, window
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )

router = APIRouter()


def _get_db():
    return next(get_session())


@router.get("/config")
async def get_auth_config(request: Request):
    """Public endpoint: returns auth configuration for the frontend."""
    settings = request.app.state.settings
    return {
        "google_client_id": settings.google_client_id or "",
        "google_enabled": bool(settings.google_client_id),
    }


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterRequest, request: Request):
    await _rate_limit(request, "auth:register", max_requests=5, window=60)
    db = _get_db()
    try:
        auth_svc = AuthService(request.app.state.settings)
        try:
            user = auth_svc.register(
                db, body.username, body.email, body.password, body.display_name
            )
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        token = auth_svc.create_token(user.id)
        return AuthResponse(token=token, user=UserResponse.model_validate(user))
    finally:
        db.close()


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, request: Request):
    await _rate_limit(request, "auth:login", max_requests=10, window=60)
    db = _get_db()
    try:
        auth_svc = AuthService(request.app.state.settings)
        try:
            user = auth_svc.authenticate(db, body.username, body.password)
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e))
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = auth_svc.create_token(user.id)
        return AuthResponse(token=token, user=UserResponse.model_validate(user))
    finally:
        db.close()


@router.post("/google", response_model=AuthResponse)
async def google_auth(body: GoogleAuthRequest, request: Request):
    """Authenticate with Google ID token. Creates account if new user."""
    await _rate_limit(request, "auth:google", max_requests=10, window=60)

    settings = request.app.state.settings
    if not settings.google_client_id:
        raise HTTPException(
            status_code=501,
            detail="Google Sign-In is not configured on this server",
        )

    db = _get_db()
    try:
        auth_svc = AuthService(settings)
        try:
            user = auth_svc.google_authenticate(
                db, body.credential, settings.google_client_id
            )
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e))
        token = auth_svc.create_token(user.id)
        return AuthResponse(token=token, user=UserResponse.model_validate(user))
    finally:
        db.close()


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, request: Request):
    """Generate a 6-digit reset code for password recovery.

    The code is stored server-side only. In development, it is logged at
    DEBUG level. In production, integrate an email provider to deliver it.
    """
    await _rate_limit(request, "auth:forgot", max_requests=5, window=60)
    db = _get_db()
    try:
        auth_svc = AuthService(request.app.state.settings)
        try:
            code = auth_svc.generate_reset_code(db, body.email)
            # DEV ONLY: log the code so developers can test the flow.
            # Remove this line or gate behind a CB_DEBUG flag before production.
            logger.debug("DEV reset code for %s: %s", body.email, code)
        except ValueError:
            # Swallow error — return the same response whether the email
            # exists or not, to prevent user enumeration.
            pass
        return {"message": "If an account exists with that email, a verification code has been sent."}
    finally:
        db.close()


@router.post("/reset-password", response_model=AuthResponse)
async def reset_password(body: ResetPasswordRequest, request: Request):
    """Verify the reset code and set a new password."""
    await _rate_limit(request, "auth:reset", max_requests=5, window=60)
    db = _get_db()
    try:
        auth_svc = AuthService(request.app.state.settings)
        try:
            user = auth_svc.verify_reset_code(
                db, body.email, body.code, body.new_password
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        token = auth_svc.create_token(user.id)
        return AuthResponse(token=token, user=UserResponse.model_validate(user))
    finally:
        db.close()


@router.get("/me", response_model=UserResponse)
async def get_profile(request: Request):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    return UserResponse.model_validate(user)


@router.put("/me", response_model=UserResponse)
async def update_profile(body: ProfileUpdateRequest, request: Request):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        db_user = db.query(UserRecord).filter(UserRecord.id == user.id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        if body.display_name is not None:
            db_user.display_name = body.display_name
        if body.avatar_url is not None:
            db_user.avatar_url = body.avatar_url
        if body.linked_member_id is not None:
            db_user.linked_member_id = body.linked_member_id
        if body.skills is not None:
            db_user.skills = body.skills
        if body.role_title is not None:
            db_user.role_title = body.role_title
        if body.bio is not None:
            db_user.bio = body.bio
        db.commit()
        db.refresh(db_user)
        return UserResponse.model_validate(db_user)
    finally:
        db.close()


@router.get("/users", response_model=list[UserResponse])
async def list_users(request: Request):
    from app.dependencies import get_current_user

    get_current_user(request)
    db = _get_db()
    try:
        users = (
            db.query(UserRecord).filter(UserRecord.is_active == True).all()  # noqa: E712
        )
        return [UserResponse.model_validate(u) for u in users]
    finally:
        db.close()
