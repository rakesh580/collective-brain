"""ORM model for the digest_log table — audit trail of digest deliveries."""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String

from app.db.database import Base


class DigestLog(Base):
    __tablename__ = "digest_log"

    id = Column(String, primary_key=True)
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workspace_id = Column(String, nullable=True, index=True)
    channel_id = Column(String, nullable=True)
    # "slack" | "email" | "in_app"
    delivery_channel = Column(String, nullable=False)
    recipient = Column(String, nullable=True)
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    # "sent" | "failed" | "skipped"
    status = Column(String, nullable=False)
    error = Column(String, nullable=True)
    sent_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
