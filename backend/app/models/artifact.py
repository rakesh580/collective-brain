from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String

from app.db.database import Base


class ArtifactRecord(Base):
    __tablename__ = "artifacts"

    id = Column(String, primary_key=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    source_type = Column(String, nullable=False, index=True)
    source_path = Column(String, nullable=False)
    title = Column(String, nullable=True)
    ingested_at = Column(DateTime, default=lambda: datetime.now(UTC))
    chunk_count = Column(Integer, default=0)
    member_ids = Column(JSON, default=list)
    metadata_json = Column(JSON, default=dict)
    status = Column(String, default="completed")
    room_id = Column(String, ForeignKey("chat_rooms.id"), nullable=True, index=True)

    # ── Phase 5: external source tracking ────────────────────────────────────
    # URL of the source document (e.g. Notion page URL, Google Doc URL)
    source_url = Column(String(2048), nullable=True)
    # Unique ID in the external system (page_id, doc_id, etc.)
    external_id = Column(String(512), nullable=True, index=True)
    # SHA-256 of the raw content — used to skip re-ingestion when nothing changed
    content_hash = Column(String(64), nullable=True, index=True)
    # When the external source was last synced
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

    # ── Phase 6: public knowledge base ────────────────────────────────────────
    is_public = Column(Boolean, nullable=True, default=False)
