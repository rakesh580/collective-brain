from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStoreService
from app.services.llm_service import LLMService
from app.db.database import create_session


def get_db() -> Session:
    """Create a new DB session. Caller MUST close it (use try/finally)."""
    return create_session()


def get_embedding_service(request: Request) -> EmbeddingService:
    return request.app.state.embedding_service


def get_vector_store(request: Request) -> VectorStoreService:
    return request.app.state.vector_store


def get_llm_service(request: Request) -> LLMService:
    return request.app.state.llm_service


def get_current_user(request: Request):
    """Extract and validate user from Authorization: Bearer <token> header."""
    from app.models.user import UserRecord
    from app.services.auth_service import AuthService

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    token = auth_header.split(" ", 1)[1]
    settings = request.app.state.settings
    auth_svc = AuthService(settings)
    user_id = auth_svc.decode_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    db = get_db()
    try:
        user = (
            db.query(UserRecord)
            .filter(UserRecord.id == user_id, UserRecord.is_active == True)  # noqa: E712
            .first()
        )
        if user:
            db.expunge(user)
    finally:
        db.close()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


def get_optional_user(request: Request):
    """Same as get_current_user but returns None instead of raising 401."""
    try:
        return get_current_user(request)
    except HTTPException:
        return None


def require_role(*allowed_roles: str):
    """Dependency factory that checks the current user has one of the allowed roles.

    Usage in a route:
        @router.delete("/thing/{id}")
        async def delete_thing(request: Request, user=Depends(require_role("admin"))):
            ...
    """
    def checker(request: Request):
        user = get_current_user(request)
        user_role = getattr(user, "role", None) or "member"
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user
    return checker
