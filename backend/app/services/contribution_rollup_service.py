"""Nightly ContributionRollup job.

For every member with recent activity, compute per-window stats and persist
one ``ContributionRollup`` row per (member, window). This backs:

- Dashboard "this week vs last week" deltas (diff two 7d rollups).
- Member profile strengths/weaknesses chips.
- Pulse "silent area" signals (member with 30d>0 but 7d==0 on a topic).

Defaults: rollup windows are 7 and 30 days. Jobs running on the same UTC
day overwrite (upsert by (member_id, window_days, computed_at)).
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.contribution import ContributionRecord
from app.models.contribution_rollup import ContributionRollup
from app.models.member import MemberRecord

logger = logging.getLogger("collective_brain.contribution_rollup")

DEFAULT_WINDOWS = (7, 30)


def _floor_to_day(ts: datetime) -> datetime:
    return ts.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC)


def _member_window_stats(db: Session, member_id: str, window_days: int, now: datetime) -> dict[str, Any]:
    cutoff = now - timedelta(days=window_days)
    rows = (
        db.query(ContributionRecord)
        .filter(
            ContributionRecord.member_id == member_id,
            ContributionRecord.timestamp >= cutoff,
        )
        .all()
    )

    topic_counter: Counter[str] = Counter()
    type_counter: Counter[str] = Counter()
    artifact_ids: set[str] = set()
    last_activity: datetime | None = None

    for r in rows:
        for t in r.topics or []:
            if t:
                topic_counter[str(t)] += 1
        if r.contribution_type:
            type_counter[r.contribution_type] += 1
        if r.artifact_id:
            artifact_ids.add(r.artifact_id)
        if r.timestamp and (last_activity is None or r.timestamp > last_activity):
            last_activity = r.timestamp

    top_topic = topic_counter.most_common(1)[0][0] if topic_counter else None
    return {
        "contributions_count": len(rows),
        "artifacts_touched": len(artifact_ids),
        "distinct_topics": len(topic_counter),
        "topic_histogram": dict(topic_counter.most_common(10)),
        "top_topic": top_topic,
        "type_histogram": dict(type_counter),
        "last_activity_at": last_activity,
    }


def _upsert_rollup(
    db: Session,
    *,
    member: MemberRecord,
    window_days: int,
    computed_at: datetime,
    stats: dict[str, Any],
) -> ContributionRollup:
    """Replace any rollup for (member, window, same UTC day) with fresh stats."""
    day_start = _floor_to_day(computed_at)
    day_end = day_start + timedelta(days=1)

    existing = (
        db.query(ContributionRollup)
        .filter(
            ContributionRollup.member_id == member.id,
            ContributionRollup.window_days == window_days,
            ContributionRollup.computed_at >= day_start,
            ContributionRollup.computed_at < day_end,
        )
        .first()
    )

    if existing is None:
        rollup = ContributionRollup(
            id=str(uuid.uuid4()),
            member_id=member.id,
            organization_id=getattr(member, "organization_id", None),
            window_days=window_days,
            computed_at=computed_at,
            **stats,
        )
        db.add(rollup)
        return rollup

    existing.computed_at = computed_at
    existing.organization_id = getattr(member, "organization_id", None)
    for key, value in stats.items():
        setattr(existing, key, value)
    return existing


def compute_and_save_rollups(
    db: Session,
    windows: tuple[int, ...] = DEFAULT_WINDOWS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Iterate every member and persist rollups for each configured window.

    Returns a summary dict so the scheduled run has a usable result payload.
    """
    current = now or datetime.now(UTC)
    members = db.query(MemberRecord).all()

    rows_written = 0
    for member in members:
        for window in windows:
            stats = _member_window_stats(db, member.id, window, current)
            # Skip members with zero activity in the largest window to keep
            # the table from blowing up on inactive users.
            if window == max(windows) and stats["contributions_count"] == 0:
                continue
            _upsert_rollup(
                db,
                member=member,
                window_days=window,
                computed_at=current,
                stats=stats,
            )
            rows_written += 1

    db.commit()

    summary = {
        "members_processed": len(members),
        "windows": list(windows),
        "rows_written": rows_written,
        "computed_at": current.isoformat(),
    }
    logger.info(
        "ContributionRollup complete: members=%d windows=%s rows=%d",
        summary["members_processed"],
        windows,
        rows_written,
    )
    return summary


def run_contribution_rollup_job() -> dict[str, Any]:
    """Scheduler entrypoint — opens its own session."""
    from app.db.database import create_session

    db = create_session()
    try:
        return compute_and_save_rollups(db)
    finally:
        db.close()
