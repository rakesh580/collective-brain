"""AuditService — write immutable audit log entries.

Usage:
    from app.services.audit_service import AuditService
    AuditService.log(db, action="auth.login", user_id=user.id, ...)
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

logger = logging.getLogger("collective_brain.audit")


class AuditService:
    @staticmethod
    def log(
        db: Session,
        *,
        action: str,
        user_id: str | None = None,
        organization_id: str | None = None,
        actor: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        result: str = "ok",
        detail: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Write one audit log entry.  Never raises — failures are logged, not propagated."""
        entry = AuditLog(
            id=str(uuid.uuid4()),
            action=action,
            user_id=user_id,
            organization_id=organization_id,
            actor=actor,
            target_type=target_type,
            target_id=target_id,
            ip_address=ip_address,
            user_agent=user_agent,
            result=result,
            detail=detail or {},
            created_at=datetime.now(UTC),
        )
        try:
            db.add(entry)
            db.commit()
            db.refresh(entry)
        except Exception as exc:
            logger.error("Failed to write audit log: %s", exc)
            db.rollback()
        return entry

    @staticmethod
    def from_request(request) -> dict[str, str | None]:
        """Extract ip_address and user_agent from a FastAPI Request object."""
        ip = None
        if request:
            forwarded = request.headers.get("x-forwarded-for")
            ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)
        return {
            "ip_address": ip,
            "user_agent": request.headers.get("user-agent") if request else None,
        }

    @staticmethod
    def list(
        db: Session,
        *,
        organization_id: str | None = None,
        user_id: str | None = None,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLog]:
        q = db.query(AuditLog)
        if organization_id:
            q = q.filter(AuditLog.organization_id == organization_id)
        if user_id:
            q = q.filter(AuditLog.user_id == user_id)
        if action:
            q = q.filter(AuditLog.action == action)
        return q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
