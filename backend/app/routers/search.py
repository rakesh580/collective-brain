from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_

from app.db.database import create_session
from app.dependencies import get_current_user
from app.models.artifact import ArtifactRecord
from app.models.insight import InsightRecord
from app.models.member import MemberRecord
from app.models.room import ChatRoom

router = APIRouter()


def _get_db():
    return create_session()


@router.get("")
async def search(
    request: Request,
    q: str,
    room_id: str | None = None,
    limit: int = 20,
    semantic: bool = False,
    user=Depends(get_current_user),
):
    """Cross-entity search across members, artifacts, insights, and rooms using SQL ILIKE.

    When semantic=true, also performs embedding-based vector search and includes
    the results under a ``"semantic"`` key.
    """
    db = _get_db()
    try:
        # Escape ILIKE special characters to prevent false matches
        escaped_q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped_q}%"
        results = {"members": [], "artifacts": [], "insights": [], "rooms": []}

        # Search members using SQL ILIKE (name match)
        member_query = db.query(MemberRecord).filter(MemberRecord.name.ilike(pattern)).limit(limit)
        for m in member_query.all():
            results["members"].append(
                {
                    "id": m.id,
                    "name": m.name,
                    "expertise_tags": m.expertise_tags or [],
                    "total_contributions": m.total_contributions or 0,
                }
            )

        # Search artifacts using SQL ILIKE (scoped by room_id if provided)
        art_conditions = [
            ArtifactRecord.title.ilike(pattern),
            ArtifactRecord.source_path.ilike(pattern),
            ArtifactRecord.source_type.ilike(pattern),
        ]
        art_query = db.query(ArtifactRecord).filter(or_(*art_conditions))
        if room_id:
            art_query = art_query.filter(ArtifactRecord.room_id == room_id)
        for a in art_query.limit(limit).all():
            results["artifacts"].append(
                {
                    "id": a.id,
                    "title": a.title,
                    "source_type": a.source_type,
                    "source_path": a.source_path,
                    "ingested_at": a.ingested_at.isoformat() if a.ingested_at else None,
                    "chunk_count": a.chunk_count or 0,
                }
            )

        # Search insights using SQL ILIKE (scoped by room_id if provided)
        ins_conditions = [
            InsightRecord.title.ilike(pattern),
            InsightRecord.body.ilike(pattern),
        ]
        ins_query = db.query(InsightRecord).filter(or_(*ins_conditions)).order_by(InsightRecord.generated_at.desc())
        if room_id:
            ins_query = ins_query.filter(InsightRecord.room_id == room_id)
        for i in ins_query.limit(limit).all():
            results["insights"].append(
                {
                    "id": i.id,
                    "insight_type": i.insight_type,
                    "title": i.title,
                    "body": (i.body or "")[:200],
                    "generated_at": i.generated_at.isoformat() if i.generated_at else None,
                    "confidence": i.confidence or 0,
                }
            )

        # Search public rooms using SQL ILIKE
        room_conditions = [
            ChatRoom.name.ilike(pattern),
            ChatRoom.description.ilike(pattern),
        ]
        room_query = (
            db.query(ChatRoom)
            .filter(ChatRoom.is_public == True)  # noqa: E712
            .filter(or_(*room_conditions))
        )
        for r in room_query.limit(limit).all():
            results["rooms"].append(
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "is_public": r.is_public,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
            )

        # Semantic (vector) search when requested
        if semantic:
            results["semantic"] = _perform_semantic_search(request, q, n_results=limit, room_id=room_id)

        return {
            "query": q,
            "results": results,
            "counts": {k: len(v) for k, v in results.items()},
        }
    finally:
        db.close()


def _perform_semantic_search(
    request: Request, query: str, n_results: int = 20, room_id: str | None = None
) -> list[dict]:
    """Run embedding-based vector search and return results with scores."""
    embedder = request.app.state.embedding_service
    vs = request.app.state.vector_store

    query_embedding = embedder.embed(query)

    kwargs: dict = {"query_embedding": query_embedding, "n_results": n_results}
    if room_id:
        kwargs["room_id"] = room_id

    raw = vs.query(**kwargs)

    # Normalise the vector store response into a list of dicts.
    # ChromaDB-style results come back as a dict of lists; other stores
    # may already return a list of dicts.
    if isinstance(raw, dict):
        ids = raw.get("ids", [[]])[0] if raw.get("ids") else []
        documents = raw.get("documents", [[]])[0] if raw.get("documents") else []
        distances = raw.get("distances", [[]])[0] if raw.get("distances") else []
        metadatas = raw.get("metadatas", [[]])[0] if raw.get("metadatas") else []
        results = []
        for idx in range(len(ids)):
            results.append(
                {
                    "id": ids[idx],
                    "document": documents[idx] if idx < len(documents) else "",
                    "score": distances[idx] if idx < len(distances) else None,
                    "metadata": metadatas[idx] if idx < len(metadatas) else {},
                }
            )
        return results
    # Already a list
    return raw


@router.get("/semantic")
async def search_semantic(
    request: Request, q: str, room_id: str | None = None, limit: int = 20, user=Depends(get_current_user)
):
    """Dedicated semantic search endpoint returning only vector search results with scores."""
    results = _perform_semantic_search(request, q, n_results=limit, room_id=room_id)
    return {
        "query": q,
        "results": results,
        "count": len(results),
    }
