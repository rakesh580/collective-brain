from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Float, JSON
from app.db.database import Base


class MemberRecord(Base):
    __tablename__ = "members"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    aliases = Column(JSON, default=list)
    email = Column(String, nullable=True)
    expertise_tags = Column(JSON, default=list)
    expertise_scores = Column(JSON, default=dict)
    strengths = Column(JSON, default=list)
    weaknesses = Column(JSON, default=list)
    first_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_active = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    total_contributions = Column(Float, default=0)
    metadata_json = Column(JSON, default=dict)
