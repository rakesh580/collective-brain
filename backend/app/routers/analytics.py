from datetime import datetime, timedelta
from fastapi import APIRouter, Request
from sqlalchemy import func, cast, Date

from app.models.member import MemberRecord
from app.models.artifact import ArtifactRecord
from app.models.contribution import ContributionRecord
from app.db.database import get_session

router = APIRouter()


def _get_db():
    return next(get_session())


@router.get("/activity-timeline")
async def get_activity_timeline(request: Request, days: int = 30, room_id: str | None = None):
    """Daily contribution counts for the last N days using SQL aggregation."""
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Use SQL GROUP BY date for aggregation
        query = (
            db.query(
                cast(ContributionRecord.timestamp, Date).label("day"),
                func.count().label("cnt"),
            )
            .filter(ContributionRecord.timestamp >= cutoff)
        )
        if room_id:
            query = query.filter(ContributionRecord.room_id == room_id)
        daily_rows = query.group_by("day").all()

        daily = {str(row.day): row.cnt for row in daily_rows}

        # Fill in missing days
        timeline = []
        current = cutoff.date()
        today = datetime.utcnow().date()
        total = 0
        while current <= today:
            day_str = current.strftime("%Y-%m-%d")
            count = daily.get(day_str, 0)
            timeline.append({"date": day_str, "count": count})
            total += count
            current += timedelta(days=1)

        return {"timeline": timeline, "total": total}
    finally:
        db.close()


@router.get("/source-breakdown")
async def get_source_breakdown(request: Request, room_id: str | None = None):
    """Artifact counts by source type using SQL aggregation."""
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        # SQL GROUP BY for source type counts
        query = db.query(
            ArtifactRecord.source_type,
            func.count().label("artifact_count"),
            func.coalesce(func.sum(ArtifactRecord.chunk_count), 0).label("total_chunks"),
        )
        if room_id:
            query = query.filter(ArtifactRecord.room_id == room_id)
        rows = query.group_by(ArtifactRecord.source_type).all()

        total_artifacts = sum(r.artifact_count for r in rows)
        total_chunks = sum(r.total_chunks for r in rows)

        return {
            "sources": [
                {"source_type": r.source_type, "artifact_count": r.artifact_count}
                for r in sorted(rows, key=lambda x: x.artifact_count, reverse=True)
            ],
            "total_artifacts": total_artifacts,
            "total_chunks": total_chunks,
        }
    finally:
        db.close()


@router.get("/expertise-matrix")
async def get_expertise_matrix(request: Request, room_id: str | None = None):
    """Member expertise scores as a matrix for heatmap visualization."""
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        if room_id:
            # Only members with contributions in this room
            member_ids = [
                mid for (mid,) in
                db.query(ContributionRecord.member_id)
                .filter(ContributionRecord.room_id == room_id)
                .distinct()
                .all()
            ]
            members = (
                db.query(MemberRecord)
                .filter(MemberRecord.id.in_(member_ids))
                .order_by(MemberRecord.total_contributions.desc())
                .limit(20)
                .all()
            ) if member_ids else []
        else:
            members = (
                db.query(MemberRecord)
                .filter(MemberRecord.total_contributions > 0)
                .order_by(MemberRecord.total_contributions.desc())
                .limit(20)
                .all()
            )

        # Collect all unique topics
        all_topics: set[str] = set()
        for m in members:
            all_topics.update((m.expertise_scores or {}).keys())

        # Build matrix
        top_topics = sorted(all_topics)[:15]  # Cap at 15 topics
        matrix = []
        for m in members:
            scores = m.expertise_scores or {}
            row = {
                "member_id": m.id,
                "member_name": m.name,
                "scores": {t: round(scores.get(t, 0), 2) for t in top_topics},
            }
            matrix.append(row)

        return {"topics": top_topics, "members": matrix}
    finally:
        db.close()


@router.get("/contribution-types")
async def get_contribution_types(request: Request, room_id: str | None = None):
    """Contribution breakdown by type using SQL aggregation."""
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        query = db.query(
            ContributionRecord.contribution_type,
            func.count().label("cnt"),
        )
        if room_id:
            query = query.filter(ContributionRecord.room_id == room_id)
        rows = query.group_by(ContributionRecord.contribution_type).all()

        total = sum(r.cnt for r in rows)
        return {
            "types": [
                {"type": r.contribution_type, "count": r.cnt}
                for r in sorted(rows, key=lambda x: x.cnt, reverse=True)
            ],
            "total": total,
        }
    finally:
        db.close()


@router.get("/member-activity")
async def get_member_activity(request: Request, days: int = 30, room_id: str | None = None):
    """Per-member contribution counts over last N days using SQL aggregation."""
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        # SQL GROUP BY member_id for counts
        query = (
            db.query(
                ContributionRecord.member_id,
                func.count().label("cnt"),
            )
            .filter(ContributionRecord.timestamp >= cutoff)
        )
        if room_id:
            query = query.filter(ContributionRecord.room_id == room_id)
        rows = query.group_by(ContributionRecord.member_id).all()

        # Resolve member names in one query
        member_ids = [r.member_id for r in rows if r.member_id]
        members = (
            db.query(MemberRecord)
            .filter(MemberRecord.id.in_(member_ids))
            .all()
        ) if member_ids else []
        name_map = {m.id: m.name for m in members}

        activity = sorted(
            [
                {
                    "member_id": r.member_id or "unknown",
                    "member_name": name_map.get(r.member_id, r.member_id or "unknown"),
                    "contributions": r.cnt,
                }
                for r in rows
            ],
            key=lambda x: x["contributions"],
            reverse=True,
        )

        return {"activity": activity, "period_days": days}
    finally:
        db.close()


@router.get("/topic-trends")
async def get_topic_trends(request: Request, days: int = 30, room_id: str | None = None):
    """Most common topics in recent contributions."""
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = db.query(ContributionRecord.topics).filter(
            ContributionRecord.timestamp >= cutoff
        )
        if room_id:
            query = query.filter(ContributionRecord.room_id == room_id)

        # Topics are stored as JSON arrays — need Python-side counting
        # but we only fetch the topics column, not full records
        from collections import Counter
        topic_counts: Counter = Counter()
        for (topics,) in query.all():
            for topic in (topics or []):
                topic_counts[topic] += 1

        return {
            "topics": [
                {"topic": k, "count": v}
                for k, v in topic_counts.most_common(20)
            ],
            "period_days": days,
        }
    finally:
        db.close()
