"""ORM model for the contribution_rollups table.

Per-member, per-window precomputed snapshots of recent activity. A nightly
scheduler job (ContributionRollup) writes one row per (member, window).

Downstream uses:
- Dashboard "this week vs last week" deltas
- Pulse signals (e.g. "silent area" detection)
- Member profile "strengths" / "weaknesses" chips
"""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from app.db.database import Base


class ContributionRollup(Base):
    __tablename__ = "contribution_rollups"

    id = Column(String, primary_key=True)
    member_id = Column(
        String,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Window length in days, typically 7 or 30.
    window_days = Column(Integer, nullable=False)
    # The timestamp of the rollup run (end of window).
    computed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)

    contributions_count = Column(Integer, nullable=False, default=0)
    artifacts_touched = Column(Integer, nullable=False, default=0)
    distinct_topics = Column(Integer, nullable=False, default=0)
    # {topic_name: count, ...} — top 10 topics by count in the window.
    topic_histogram = Column(JSON, nullable=False, default=dict)
    top_topic = Column(String, nullable=True)
    # Breakdown by contribution_type (git_commit, github_pr, slack_msg, ...).
    type_histogram = Column(JSON, nullable=False, default=dict)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # One row per (member, window, run-day). Two runs in the same UTC day
        # will overwrite each other; the service handles that via upsert.
        UniqueConstraint(
            "member_id", "window_days", "computed_at", name="uq_rollup_member_window_at"
        ),
        Index("ix_rollups_member_window", "member_id", "window_days"),
    )
