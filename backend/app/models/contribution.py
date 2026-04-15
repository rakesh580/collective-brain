from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class ContributionRecord(Base):
    __tablename__ = "contributions"

    id = Column(String, primary_key=True)
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    member_id = Column(String, ForeignKey("members.id", ondelete="CASCADE"), index=True)
    artifact_id = Column(String, ForeignKey("artifacts.id"))
    contribution_type = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    description = Column(Text)
    topics = Column(JSON, default=list)
    sentiment = Column(Float, nullable=True)
    impact_score = Column(Float, default=0.0)
    metadata_json = Column(JSON, default=dict)
    room_id = Column(String, ForeignKey("chat_rooms.id"), nullable=True, index=True)

    member = relationship("MemberRecord", back_populates="contributions")
