"""ORM model for the health_snapshots table (BUG-017 fix)."""
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey
from app.db.database import Base


class HealthSnapshot(Base):
    __tablename__ = "health_snapshots"

    id = Column(String, primary_key=True)
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    bus_factor_count = Column(Integer, default=0)
    coverage_pct = Column(Float, default=0.0)
    collab_density = Column(Float, default=0.0)
    active_member_pct = Column(Float, default=0.0)
    avg_breadth = Column(Float, default=0.0)
    health_score = Column(Float, default=0.0)
    risk_summary = Column(Text, default="{}")  # JSON-encoded dict stored as text
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
