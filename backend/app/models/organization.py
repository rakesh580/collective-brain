from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.database import Base


class OrganizationRecord(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True, index=True)  # URL-safe identifier
    plan = Column(String, nullable=False, default="free")  # "free", "pro", "enterprise"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    settings_json = Column(JSON, default=dict)   # org-level config (SSO, branding, etc.)
    metadata_json = Column(JSON, default=dict)

    memberships = relationship(
        "OrganizationMembership",
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class OrganizationMembership(Base):
    """Links users to organizations with a role."""
    __tablename__ = "organization_memberships"

    id = Column(String, primary_key=True)
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # "owner" — full control, "admin" — manage members/settings, "member" — standard access
    role = Column(String, nullable=False, default="member")
    joined_at = Column(DateTime, default=lambda: datetime.now(UTC))

    organization = relationship("OrganizationRecord", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_membership"),
    )
