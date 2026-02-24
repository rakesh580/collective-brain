from datetime import datetime, timedelta
from collections import Counter
from fastapi import APIRouter, Request

from app.models.member import MemberRecord
from app.models.artifact import ArtifactRecord
from app.models.contribution import ContributionRecord
from app.models.insight import InsightRecord
from app.db.database import get_session

router = APIRouter()


def _get_db():
    return next(get_session())


@router.get("/activity-timeline")
async def get_activity_timeline(request: Request, days: int = 30):
    """Daily contribution counts for the last N days."""
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        contribs = (
            db.query(ContributionRecord)
            .filter(ContributionRecord.timestamp >= cutoff)
            .all()
        )

        daily: dict[str, int] = {}
        for c in contribs:
            if c.timestamp:
                day = c.timestamp.strftime("%Y-%m-%d")
                daily[day] = daily.get(day, 0) + 1

        # Fill in missing days
        timeline = []
        current = cutoff.date()
        today = datetime.utcnow().date()
        while current <= today:
            day_str = current.strftime("%Y-%m-%d")
            timeline.append({"date": day_str, "count": daily.get(day_str, 0)})
            current += timedelta(days=1)

        return {"timeline": timeline, "total": sum(daily.values())}
    finally:
        db.close()


@router.get("/source-breakdown")
async def get_source_breakdown(request: Request):
    """Artifact counts by source type."""
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        artifacts = db.query(ArtifactRecord).all()
        breakdown = Counter(a.source_type for a in artifacts)
        total_chunks = sum(a.chunk_count or 0 for a in artifacts)
        return {
            "sources": [
                {"source_type": k, "artifact_count": v}
                for k, v in breakdown.most_common()
            ],
            "total_artifacts": len(artifacts),
            "total_chunks": total_chunks,
        }
    finally:
        db.close()


@router.get("/expertise-matrix")
async def get_expertise_matrix(request: Request):
    """Member expertise scores as a matrix for heatmap visualization."""
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
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
async def get_contribution_types(request: Request):
    """Contribution breakdown by type."""
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        contribs = db.query(ContributionRecord).all()
        type_counts = Counter(c.contribution_type for c in contribs)
        return {
            "types": [
                {"type": k, "count": v}
                for k, v in type_counts.most_common()
            ],
            "total": len(contribs),
        }
    finally:
        db.close()


@router.get("/member-activity")
async def get_member_activity(request: Request, days: int = 30):
    """Per-member contribution counts over last N days."""
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        contribs = (
            db.query(ContributionRecord)
            .filter(ContributionRecord.timestamp >= cutoff)
            .all()
        )

        member_counts: dict[str, int] = {}
        for c in contribs:
            mid = c.member_id or "unknown"
            member_counts[mid] = member_counts.get(mid, 0) + 1

        # Resolve member names
        member_ids = list(member_counts.keys())
        members = (
            db.query(MemberRecord)
            .filter(MemberRecord.id.in_(member_ids))
            .all()
        )
        name_map = {m.id: m.name for m in members}

        activity = sorted(
            [
                {
                    "member_id": mid,
                    "member_name": name_map.get(mid, mid),
                    "contributions": count,
                }
                for mid, count in member_counts.items()
            ],
            key=lambda x: x["contributions"],
            reverse=True,
        )

        return {"activity": activity, "period_days": days}
    finally:
        db.close()


@router.get("/topic-trends")
async def get_topic_trends(request: Request, days: int = 30):
    """Most common topics in recent contributions."""
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        contribs = (
            db.query(ContributionRecord)
            .filter(ContributionRecord.timestamp >= cutoff)
            .all()
        )

        topic_counts: Counter = Counter()
        for c in contribs:
            for topic in (c.topics or []):
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
