from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Float, JSON
from app.db.database import Base


class InsightRecord(Base):
    __tablename__ = "insights"

    id = Column(String, primary_key=True)
    insight_type = Column(String)
    title = Column(String)
    body = Column(Text)
    generated_at = Column(DateTime, default=datetime.utcnow)
    related_member_ids = Column(JSON, default=list)
    confidence = Column(Float, default=0.0)
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, default=dict)
