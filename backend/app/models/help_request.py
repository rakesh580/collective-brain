"""ORM model for the help_requests table (BUG-017 fix)."""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text

from app.db.database import Base


class HelpRequest(Base):
    __tablename__ = "help_requests"

    id = Column(String, primary_key=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    requester_user_id = Column(String, nullable=False, index=True)
    expert_member_id = Column(String, nullable=False, index=True)
    query = Column(Text, nullable=False)
    topics = Column(Text, default="[]")  # JSON-encoded list stored as text
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    resolved_at = Column(DateTime, nullable=True)
