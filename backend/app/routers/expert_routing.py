"""Expert Routing — "Who Should I Talk To?" feature.

Given a natural-language query, finds the best-matched experts using the
knowledge graph (expertise scores, PageRank, recency).  Also manages
help-request records so users can formally ask an expert for assistance.
"""

import json
import logging
import re
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.db.database import create_session
from app.models.member import MemberRecord
from app.models.user import UserRecord
from app.services.memory_graph import MemoryGraph

logger = logging.getLogger("collective_brain.expert_routing")

router = APIRouter()


# ── Request / Response Schemas ────────────────────────────────────

class HelpRequestCreate(BaseModel):
    expert_member_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1, max_length=2000)
    topics: list[str] = Field(default_factory=list)


class HelpRequestResponse(BaseModel):
    id: str
    requester_user_id: str
    expert_member_id: str
    query: str
    topics: list[str]
    status: str
    created_at: datetime
    resolved_at: datetime | None = None


class ExpertRecommendation(BaseModel):
    member_id: str
    name: str
    match_score: float
    expertise_topics: list[str]
    last_active: datetime | None = None
    availability_hint: str = "unknown"


class ExpertRecommendationResponse(BaseModel):
    experts: list[ExpertRecommendation]
    query: str
    topics: list[str]


# ── Helpers ───────────────────────────────────────────────────────

def _get_db():
    return create_session()


_STOP_WORDS = frozenset({
    "i", "me", "my", "we", "our", "you", "your", "it", "its", "he", "she",
    "they", "them", "this", "that", "the", "a", "an", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "shall", "should", "may", "might", "can", "could",
    "about", "above", "after", "before", "between", "but", "by", "for",
    "from", "in", "into", "of", "on", "or", "out", "over", "to", "under",
    "up", "with", "and", "not", "no", "so", "if", "at", "as", "how", "what",
    "who", "whom", "which", "when", "where", "why", "all", "any", "each",
    "need", "help", "know", "talk", "find", "want", "get", "someone",
    "expert", "person", "question", "about",
})


def _extract_topics(query: str) -> list[str]:
    """Simple keyword extraction: lowercase, strip punctuation, remove stop words."""
    tokens = re.findall(r"[a-zA-Z0-9#+.\-]+", query.lower())
    topics = [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]
    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for t in topics:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/recommend", response_model=ExpertRecommendationResponse)
async def recommend_experts(
    request: Request,
    query: str,
    top_k: int = 3,
    room_id: str | None = None,
):
    """Given a query, recommend the best experts to talk to."""
    from app.dependencies import get_current_user
    get_current_user(request)

    if top_k < 1:
        top_k = 1
    elif top_k > 20:
        top_k = 20

    topics = _extract_topics(query)
    if not topics:
        return ExpertRecommendationResponse(experts=[], query=query, topics=topics)

    db = _get_db()
    try:
        graph = MemoryGraph(db, room_id=room_id)
        experts = graph.find_experts_for_topics(topics, top_k=top_k)
        recommendations = [
            ExpertRecommendation(
                member_id=e["member_id"],
                name=e["name"],
                match_score=e["match_score"],
                expertise_topics=e["expertise_topics"],
                last_active=e.get("last_active"),
                availability_hint=e.get("availability_hint", "unknown"),
            )
            for e in experts
        ]
        return ExpertRecommendationResponse(experts=recommendations, query=query, topics=topics)
    finally:
        db.close()


@router.post("/request-help", response_model=HelpRequestResponse, status_code=201)
async def request_help(body: HelpRequestCreate, request: Request):
    """Store a help request — the current user asks an expert for help."""
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        # Verify the expert member exists
        member = db.query(MemberRecord).filter(MemberRecord.id == body.expert_member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="Expert member not found")

        from app.db.database import create_help_request
        help_req = create_help_request(
            db,
            requester_user_id=user.id,
            expert_member_id=body.expert_member_id,
            query=body.query,
            topics=body.topics,
        )
        return HelpRequestResponse(**help_req)
    finally:
        db.close()


@router.get("/requests", response_model=list[HelpRequestResponse])
async def list_help_requests(request: Request):
    """List help requests relevant to the current user.

    Returns requests where the user is the requester, or where the user is
    linked to the expert member.
    """
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        from app.db.database import get_help_requests
        rows = get_help_requests(db, user_id=user.id, linked_member_id=user.linked_member_id)
        return [HelpRequestResponse(**r) for r in rows]
    finally:
        db.close()
