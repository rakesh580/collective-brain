import logging
import os
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request

from app.db.database import create_session
from app.models.user import UserRecord
from app.schemas.requests import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    GoogleAccessTokenRequest,
    GoogleAuthRequest,
    LoginRequest,
    ProfileUpdateRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.schemas.responses import AuthResponse, UserResponse
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

# In-memory rate limit fallback when Redis is unavailable (LRU-bounded)
_memory_rate_limits: dict[str, list[float]] = defaultdict(list)
_MAX_RATE_LIMIT_KEYS = 10000


async def _rate_limit(request: Request, key: str, max_requests: int, window: int = 60):
    """Rate-limit by key. Uses Redis if available, in-memory fallback otherwise."""
    redis = getattr(request.app.state, "redis", None)
    if redis is not None:
        allowed, remaining = await redis.check_rate_limit(
            f"rate:{key}:{request.client.host}", max_requests, window
        )
        if allowed is not None:
            if not allowed:
                raise HTTPException(status_code=429, detail="Too many requests")
            return

    # Redis unavailable — use in-memory fallback
    now = time.monotonic()
    mem_key = f"rate:{key}:{request.client.host}"
    _memory_rate_limits[mem_key] = [t for t in _memory_rate_limits[mem_key] if now - t < window]
    if len(_memory_rate_limits[mem_key]) >= max_requests:
        raise HTTPException(status_code=429, detail="Too many requests")
    _memory_rate_limits[mem_key].append(now)
    # Prevent unbounded memory growth
    if len(_memory_rate_limits) > _MAX_RATE_LIMIT_KEYS:
        oldest_keys = sorted(_memory_rate_limits, key=lambda k: _memory_rate_limits[k][-1] if _memory_rate_limits[k] else 0)
        for k in oldest_keys[:len(oldest_keys) // 2]:
            del _memory_rate_limits[k]

router = APIRouter()


def _get_db():
    return create_session()


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
        refresh_token = auth_svc.create_refresh_token(user.id)
        return AuthResponse(token=token, refresh_token=refresh_token, user=UserResponse.model_validate(user))
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
        refresh_token = auth_svc.create_refresh_token(user.id)
        return AuthResponse(token=token, refresh_token=refresh_token, user=UserResponse.model_validate(user))
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
        refresh_token = auth_svc.create_refresh_token(user.id)
        return AuthResponse(token=token, refresh_token=refresh_token, user=UserResponse.model_validate(user))
    finally:
        db.close()


@router.post("/google-token", response_model=AuthResponse)
async def google_access_token_auth(body: GoogleAccessTokenRequest, request: Request):
    """Authenticate with a Google access token (for iframe/popup OAuth flow)."""
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
            user = auth_svc.google_authenticate_access_token(
                db, body.access_token
            )
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e))
        token = auth_svc.create_token(user.id)
        refresh_token = auth_svc.create_refresh_token(user.id)
        return AuthResponse(token=token, refresh_token=refresh_token, user=UserResponse.model_validate(user))
    finally:
        db.close()


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, request: Request):
    """Generate an 8-character reset code for password recovery.

    The code is stored server-side only. In development, it is logged at
    DEBUG level. In production, integrate an email provider to deliver it.
    """
    await _rate_limit(request, "auth:forgot", max_requests=5, window=60)
    db = _get_db()
    try:
        auth_svc = AuthService(request.app.state.settings)
        code = None
        try:
            code = auth_svc.generate_reset_code(db, body.email)
            pass  # code is sent via email in production
        except ValueError:
            # Swallow error — return the same response whether the email
            # exists or not, to prevent user enumeration.
            pass
        resp: dict = {"message": "If an account exists with that email, a verification code has been sent."}
        # In dev/demo mode, return the code in the response so users can
        # test password reset without an email provider.
        if os.environ.get("CB_DEV_MODE") == "1" and code:
            resp["code"] = code
        return resp
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
        refresh_token = auth_svc.create_refresh_token(user.id)
        return AuthResponse(token=token, refresh_token=refresh_token, user=UserResponse.model_validate(user))
    finally:
        db.close()


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(body: RefreshTokenRequest, request: Request):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    await _rate_limit(request, "auth:refresh", max_requests=30, window=60)
    auth_svc = AuthService(request.app.state.settings)
    result = auth_svc.refresh_access_token(body.refresh_token)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    new_token, new_refresh = result
    # Fetch user for response
    db = _get_db()
    try:
        from jose import jwt as _jwt
        payload = _jwt.decode(
            new_token, auth_svc.secret, algorithms=[auth_svc.algorithm]
        )
        user_id = payload.get("sub")
        user = db.query(UserRecord).filter(UserRecord.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return AuthResponse(
            token=new_token,
            refresh_token=new_refresh,
            user=UserResponse.model_validate(user),
        )
    finally:
        db.close()


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, request: Request):
    """Change the current user's password after verifying the old one."""
    from app.dependencies import get_current_user

    await _rate_limit(request, "auth:change-password", max_requests=5, window=60)

    user = get_current_user(request)
    db = _get_db()
    try:
        auth_svc = AuthService(request.app.state.settings)
        # Verify current password
        try:
            auth_svc.authenticate(db, user.username, body.current_password)
        except ValueError:
            raise HTTPException(status_code=401, detail="Current password is incorrect")

        # Set new password
        db_user = db.query(UserRecord).filter(UserRecord.id == user.id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        db_user.password_hash = auth_svc.hash_password(body.new_password)
        db.commit()
        return {"message": "Password changed successfully"}
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
