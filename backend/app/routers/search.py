from fastapi import APIRouter, Request

from app.models.member import MemberRecord
from app.models.artifact import ArtifactRecord
from app.models.insight import InsightRecord
from app.models.room import ChatRoom
from app.db.database import get_session

router = APIRouter()


def _get_db():
    return next(get_session())


@router.get("")
async def search(request: Request, q: str, room_id: str | None = None, limit: int = 20):
    """Cross-entity search across members, artifacts, insights, and rooms."""
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        query_lower = q.lower()
        results = {"members": [], "artifacts": [], "insights": [], "rooms": []}

        # Search members
        members = db.query(MemberRecord).all()
        for m in members:
            if (
                query_lower in (m.name or "").lower()
                or any(query_lower in a.lower() for a in (m.aliases or []))
                or any(query_lower in t.lower() for t in (m.expertise_tags or []))
            ):
                results["members"].append({
                    "id": m.id,
                    "name": m.name,
                    "expertise_tags": m.expertise_tags or [],
                    "total_contributions": m.total_contributions or 0,
                })

        # Search artifacts (scoped by room_id if provided)
        art_query = db.query(ArtifactRecord)
        if room_id:
            art_query = art_query.filter(ArtifactRecord.room_id == room_id)
        artifacts = art_query.all()
        for a in artifacts:
            if (
                query_lower in (a.title or "").lower()
                or query_lower in (a.source_path or "").lower()
                or query_lower in (a.source_type or "").lower()
            ):
                results["artifacts"].append({
                    "id": a.id,
                    "title": a.title,
                    "source_type": a.source_type,
                    "source_path": a.source_path,
                    "ingested_at": a.ingested_at.isoformat() if a.ingested_at else None,
                    "chunk_count": a.chunk_count or 0,
                })

        # Search insights (scoped by room_id if provided)
        ins_query = db.query(InsightRecord).order_by(InsightRecord.generated_at.desc())
        if room_id:
            ins_query = ins_query.filter(InsightRecord.room_id == room_id)
        insights = ins_query.all()
        for i in insights:
            if (
                query_lower in (i.title or "").lower()
                or query_lower in (i.body or "").lower()
            ):
                results["insights"].append({
                    "id": i.id,
                    "insight_type": i.insight_type,
                    "title": i.title,
                    "body": (i.body or "")[:200],
                    "generated_at": i.generated_at.isoformat() if i.generated_at else None,
                    "confidence": i.confidence or 0,
                })

        # Search public rooms (for discovery)
        rooms = db.query(ChatRoom).filter(ChatRoom.is_public == True).all()  # noqa: E712
        for r in rooms:
            if (
                query_lower in (r.name or "").lower()
                or query_lower in (r.description or "").lower()
            ):
                results["rooms"].append({
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "is_public": r.is_public,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                })

        # Trim to limit
        for key in results:
            results[key] = results[key][:limit]

        return {
            "query": q,
            "results": results,
            "counts": {k: len(v) for k, v in results.items()},
        }
    finally:
        db.close()
