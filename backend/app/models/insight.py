from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text

from app.db.database import Base


class InsightRecord(Base):
    __tablename__ = "insights"

    id = Column(String, primary_key=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    insight_type = Column(String, index=True)
    title = Column(String)
    body = Column(Text)
    generated_at = Column(DateTime, default=lambda: datetime.now(UTC))
    related_member_ids = Column(JSON, default=list)
    confidence = Column(Float, default=0.0)
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, default=dict)
    room_id = Column(String, ForeignKey("chat_rooms.id"), nullable=True, index=True)

    # ── Phase 5: knowledge verification ──────────────────────────────────────
    # "pending" | "verified" | "outdated" | "disputed"
    verification_status = Column(String(20), nullable=True, default="pending", index=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Artifact IDs that back this insight
    source_artifact_ids = Column(JSON, default=list)
    # How many days since the supporting artifacts were last updated
    staleness_days = Column(Integer, nullable=True)

    # ── Phase 6: public knowledge base ────────────────────────────────────────
    is_public = Column(Boolean, nullable=True, default=False)
