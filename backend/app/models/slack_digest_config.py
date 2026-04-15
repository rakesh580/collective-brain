"""ORM model for the slack_digest_config table (BUG-017 fix)."""
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.db.database import Base


class SlackDigestConfig(Base):
    __tablename__ = "slack_digest_config"

    id = Column(String, primary_key=True)
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    workspace_id = Column(String, nullable=False, index=True)
    channel_id = Column(String, nullable=False)
    channel_name = Column(String, default="")
    schedule_day = Column(Integer, default=0)
    schedule_hour = Column(Integer, default=9)
    enabled = Column(Boolean, default=True)
    last_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
