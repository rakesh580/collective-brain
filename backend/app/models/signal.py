"""ORM model for the signals table — surfaced by the pattern-detection job.

Each Signal is a flagged pattern in the org's activity — cycle-time outliers,
silent areas, bus-factor risk, review bottlenecks, Friday-land merges. The
detection job runs nightly and upserts by ``(organization_id, dedup_key)``
for any signal that is still open so we don't re-create duplicates every
night.

Lifecycle: detected → acknowledged (user saw it) → resolved (no longer
true, e.g. cycle time came back in band, a member took ownership).
"""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
)

from app.db.database import Base


class Signal(Base):
    __tablename__ = "signals"

    id = Column(String, primary_key=True)
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # slow_lane | silent_area | load_skew | friday_land | review_bottleneck
    signal_type = Column(String, nullable=False, index=True)
    # low | medium | high
    severity = Column(String, nullable=False, default="medium", index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False, default="")
    # {"work_item_ids": [...], "topic": "...", "metric": 42.0, ...}
    evidence = Column(JSON, nullable=False, default=dict)
    suggested_action = Column(String, nullable=True)

    # Used to merge repeated nightly detections of the same pattern into
    # a single open signal. Example: "slow_lane:api" — one row per topic.
    dedup_key = Column(String, nullable=False, index=True)

    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    # When someone first saw this signal. User FK omitted — we just want the id.
    acknowledged_by = Column(String, nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    # Once resolved, future detections create a NEW row instead of reopening.
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # Partial-equivalent index: detect_open queries hit this. The true
        # uniqueness guard (one OPEN signal per (org, dedup_key)) is enforced
        # in the service layer because not all supported DBs handle partial
        # unique indexes identically.
        Index("ix_signals_open_lookup", "organization_id", "dedup_key", "resolved_at"),
        Index("ix_signals_type_severity", "signal_type", "severity"),
    )
