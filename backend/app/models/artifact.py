from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey
from app.db.database import Base


class ArtifactRecord(Base):
    __tablename__ = "artifacts"

    id = Column(String, primary_key=True)
    source_type = Column(String, nullable=False)
    source_path = Column(String, nullable=False)
    title = Column(String, nullable=True)
    ingested_at = Column(DateTime, default=datetime.utcnow)
    chunk_count = Column(Integer, default=0)
    member_ids = Column(JSON, default=list)
    metadata_json = Column(JSON, default=dict)
    status = Column(String, default="completed")
    room_id = Column(String, ForeignKey("chat_rooms.id"), nullable=True, index=True)
