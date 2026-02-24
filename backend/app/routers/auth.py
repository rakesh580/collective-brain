from fastapi import APIRouter, HTTPException, Request

from app.schemas.requests import RegisterRequest, LoginRequest, ProfileUpdateRequest
from app.schemas.responses import UserResponse, AuthResponse
from app.services.auth_service import AuthService
from app.models.user import UserRecord
from app.db.database import get_session

router = APIRouter()


def _get_db():
    return next(get_session())


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterRequest, request: Request):
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
    db = _get_db()
    try:
        auth_svc = AuthService(request.app.state.settings)
        user = auth_svc.authenticate(db, body.username, body.password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
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
