from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey
from app.db.database import Base


class OffboardingReport(Base):
    __tablename__ = "offboarding_reports"

    id = Column(String, primary_key=True)
    member_id = Column(
        String, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    # Expertise areas only this member contributes to
    unique_expertise = Column(JSON, default=list)
    # Artifact IDs where this member is the sole contributor
    sole_contributor_artifact_ids = Column(JSON, default=list)
    # [{topic, recommended_member_id, recommended_member_name}]
    transfer_recommendations = Column(JSON, default=list)
    # "low" | "medium" | "high" | "critical"
    risk_level = Column(String(20), nullable=True)
    summary = Column(Text, nullable=True)
    report_data = Column(JSON, default=dict)
