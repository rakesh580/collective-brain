from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Float, JSON, ForeignKey
from app.db.database import Base


class ContributionRecord(Base):
    __tablename__ = "contributions"

    id = Column(String, primary_key=True)
    member_id = Column(String, ForeignKey("members.id"))
    artifact_id = Column(String, ForeignKey("artifacts.id"))
    contribution_type = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    description = Column(Text)
    topics = Column(JSON, default=list)
    sentiment = Column(Float, nullable=True)
    impact_score = Column(Float, default=0.0)
    metadata_json = Column(JSON, default=dict)
    room_id = Column(String, ForeignKey("chat_rooms.id"), nullable=True, index=True)
