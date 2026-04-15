from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import relationship

from app.db.database import Base


class MemberRecord(Base):
    __tablename__ = "members"

    id = Column(String, primary_key=True)
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name = Column(String, nullable=False, index=True)
    aliases = Column(JSON, default=list)
    email = Column(String, nullable=True)
    expertise_tags = Column(JSON, default=list)
    expertise_scores = Column(JSON, default=dict)
    strengths = Column(JSON, default=list)
    weaknesses = Column(JSON, default=list)
    first_seen = Column(DateTime, default=lambda: datetime.now(UTC))
    last_active = Column(DateTime, default=lambda: datetime.now(UTC))
    total_contributions = Column(Float, default=0)
    metadata_json = Column(JSON, default=dict)

    # ── Phase 6: lifecycle status ─────────────────────────────────────────────
    # "active" | "offboarding" | "offboarded"
    status = Column(String(20), nullable=True, default="active", index=True)

    contributions = relationship(
        "ContributionRecord",
        back_populates="member",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
