"""AuditLog model — immutable record of security-relevant events."""
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String

from app.db.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True)
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # What happened: "auth.login", "auth.saml_login", "auth.logout",
    # "user.created", "user.updated", "user.deleted",
    # "scim.user_provisioned", "scim.user_deprovisioned",
    # "org.sso_configured", "mfa.enabled", "mfa.verified"
    action = Column(String(100), nullable=False, index=True)

    actor = Column(String, nullable=True)       # username, "scim", "system"
    target_type = Column(String(50), nullable=True)  # "user", "org", "membership"
    target_id = Column(String, nullable=True)

    ip_address = Column(String(45), nullable=True)   # IPv4 or IPv6
    user_agent = Column(String(512), nullable=True)

    result = Column(String(20), nullable=False, default="ok")   # "ok" | "fail"
    detail = Column(JSON, default=dict)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
