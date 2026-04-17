import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.db.database import create_session
from app.dependencies import get_current_user
from app.models.artifact import ArtifactRecord
from app.models.decision import DecisionLink, DecisionRecord

logger = logging.getLogger("collective_brain.decisions")

router = APIRouter()


def _get_db():
    return create_session()


# ── Request schemas ─────────────────────────────────────────────────────────


class ExtractRequest(BaseModel):
    artifact_ids: list[str]


class WhyRequest(BaseModel):
    question: str


class LinkRequest(BaseModel):
    to_decision_id: str
    link_type: str = "related"


class DecisionUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    decision_type: str | None = None
    status: str | None = None
    context_summary: str | None = None
    alternatives_considered: list[str] | None = None
    outcome_summary: str | None = None
    tags: list[str] | None = None
    involved_member_ids: list[str] | None = None


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get("")
async def list_decisions(
    request: Request,
    decision_type: str | None = None,
    status: str | None = None,
    tag: str | None = None,
    member_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user=Depends(get_current_user),
):
    """List all decisions with optional filters."""
    db = _get_db()
    try:
        query = db.query(DecisionRecord)

        if decision_type:
            query = query.filter(DecisionRecord.decision_type == decision_type)
        if status:
            query = query.filter(DecisionRecord.status == status)
        if tag:
            # JSON array contains check — works for both PostgreSQL and SQLite
            query = query.filter(DecisionRecord.tags.contains([tag]))
        if member_id:
            query = query.filter(DecisionRecord.involved_member_ids.contains([member_id]))

        total = query.count()
        decisions = query.order_by(DecisionRecord.created_at.desc()).offset(offset).limit(limit).all()

        return {
            "decisions": [_serialize_decision(d) for d in decisions],
            "total": total,
        }
    finally:
        db.close()


@router.get("/search")
async def search_decisions_endpoint(
    request: Request,
    q: str,
    limit: int = 10,
    user=Depends(get_current_user),
):
    """Search decisions by keyword and semantic similarity."""
    from app.services.decision_search import DecisionSearchService

    llm = request.app.state.llm_service
    embedding = request.app.state.embedding_service
    vs = request.app.state.vector_store

    search_svc = DecisionSearchService(llm, embedding, vs)
    org_id = getattr(user, "organization_id", None)
    results = await search_svc.search_decisions(q, limit=limit, organization_id=org_id)

    return {
        "query": q,
        "results": results,
        "count": len(results),
    }


@router.get("/timeline")
async def decision_timeline(
    request: Request,
    topic: str,
    limit: int = 50,
    user=Depends(get_current_user),
):
    """Get chronological timeline of decisions related to a topic."""
    from app.services.decision_search import DecisionSearchService

    llm = request.app.state.llm_service
    embedding = request.app.state.embedding_service
    vs = request.app.state.vector_store

    search_svc = DecisionSearchService(llm, embedding, vs)
    org_id = getattr(user, "organization_id", None)
    timeline = await search_svc.get_decision_timeline(topic, limit=limit, organization_id=org_id)

    return {
        "topic": topic,
        "timeline": timeline,
        "count": len(timeline),
    }


# ── Decision Graph Data ──


@router.get("/graph/data")
async def get_decision_graph_data(user=Depends(get_current_user)):
    """Get decision graph data for visualization — nodes and edges."""
    db = _get_db()
    try:
        decisions = db.query(DecisionRecord).limit(200).all()
        links = db.query(DecisionLink).all()

        nodes = []
        for d in decisions:
            nodes.append(
                {
                    "id": d.id,
                    "title": d.title,
                    "type": d.decision_type,
                    "status": d.status,
                    "confidence": d.confidence_score,
                    "tags": d.tags or [],
                    "decided_at": d.decided_at.isoformat() if d.decided_at else None,
                }
            )

        edges = []
        for lnk in links:
            edges.append(
                {
                    "source": lnk.from_decision_id,
                    "target": lnk.to_decision_id,
                    "type": lnk.link_type,
                }
            )

        return {"nodes": nodes, "edges": edges}
    finally:
        db.close()


@router.get("/{decision_id}")
async def get_decision(
    decision_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    """Get a single decision with its links and context."""
    db = _get_db()
    try:
        decision = db.query(DecisionRecord).filter(DecisionRecord.id == decision_id).first()
        if not decision:
            raise HTTPException(status_code=404, detail="Decision not found")

        result = _serialize_decision(decision)

        # Get linked decisions
        from sqlalchemy import or_

        links = (
            db.query(DecisionLink)
            .filter(
                or_(
                    DecisionLink.from_decision_id == decision_id,
                    DecisionLink.to_decision_id == decision_id,
                )
            )
            .all()
        )

        linked = []
        for link in links:
            other_id = link.to_decision_id if link.from_decision_id == decision_id else link.from_decision_id
            other = db.query(DecisionRecord).filter(DecisionRecord.id == other_id).first()
            if other:
                linked.append(
                    {
                        "link_id": link.id,
                        "link_type": link.link_type,
                        "direction": "outgoing" if link.from_decision_id == decision_id else "incoming",
                        "decision": _serialize_decision(other),
                    }
                )

        result["linked_decisions"] = linked

        # Get source artifacts info
        source_artifacts = []
        artifact_ids = decision.source_artifact_ids or []
        if artifact_ids:
            artifacts = db.query(ArtifactRecord).filter(ArtifactRecord.id.in_(artifact_ids)).all()
            for a in artifacts:
                source_artifacts.append(
                    {
                        "id": a.id,
                        "title": a.title,
                        "source_type": a.source_type,
                        "source_path": a.source_path,
                        "ingested_at": a.ingested_at.isoformat() if a.ingested_at else None,
                    }
                )

        result["source_artifacts"] = source_artifacts

        return result
    finally:
        db.close()


@router.post("/extract")
async def extract_decisions(
    request: Request,
    body: ExtractRequest,
    user=Depends(get_current_user),
):
    """Trigger decision extraction from specified artifact(s)."""
    from app.services.decision_extraction import DecisionExtractionService

    llm = request.app.state.llm_service
    extraction_svc = DecisionExtractionService(llm)

    if not body.artifact_ids:
        raise HTTPException(status_code=400, detail="No artifact IDs provided")

    # Validate artifacts exist
    db = _get_db()
    try:
        existing = (
            db.query(ArtifactRecord.id)
            .filter(ArtifactRecord.id.in_(body.artifact_ids))
            .all()
        )
        existing_ids = {row.id for row in existing}
        missing = [aid for aid in body.artifact_ids if aid not in existing_ids]
        if missing:
            raise HTTPException(status_code=404, detail=f"Artifacts not found: {', '.join(missing)}")
    finally:
        db.close()

    results = await extraction_svc.extract_decisions_bulk(body.artifact_ids)
    return results


@router.post("/extract-all")
async def extract_all_decisions(
    request: Request,
    user=Depends(get_current_user),
):
    """Extract decisions from all artifacts that haven't been processed yet."""
    from app.services.decision_extraction import DecisionExtractionService

    llm = request.app.state.llm_service
    extraction_svc = DecisionExtractionService(llm)

    db = _get_db()
    try:
        # Find artifacts that don't have any decisions extracted yet
        already_processed_subq = db.query(DecisionRecord.source_artifact_ids).all()
        processed_ids = set()
        for row in already_processed_subq:
            for artifact_id in (row.source_artifact_ids or []):
                processed_ids.add(artifact_id)

        all_artifacts = db.query(ArtifactRecord.id).all()
        unprocessed_ids = [a.id for a in all_artifacts if a.id not in processed_ids]

        if not unprocessed_ids:
            return {
                "message": "All artifacts have already been processed",
                "total_artifacts": 0,
                "processed": 0,
                "total_decisions": 0,
                "decisions_by_artifact": {},
                "errors": [],
            }
    finally:
        db.close()

    logger.info("Extracting decisions from %d unprocessed artifacts", len(unprocessed_ids))
    results = await extraction_svc.extract_decisions_bulk(unprocessed_ids)
    return results


@router.post("/why")
async def why_did_we(
    request: Request,
    body: WhyRequest,
    user=Depends(get_current_user),
):
    """Answer 'why did we...' questions using the decision graph."""
    from app.services.decision_search import DecisionSearchService

    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    llm = request.app.state.llm_service
    embedding = request.app.state.embedding_service
    vs = request.app.state.vector_store

    search_svc = DecisionSearchService(llm, embedding, vs)
    org_id = getattr(user, "organization_id", None)
    result = await search_svc.why_did_we(body.question, organization_id=org_id)

    return result


@router.put("/{decision_id}")
async def update_decision(
    decision_id: str,
    body: DecisionUpdate,
    request: Request,
    user=Depends(get_current_user),
):
    """Update a decision (manual corrections)."""
    db = _get_db()
    try:
        decision = db.query(DecisionRecord).filter(DecisionRecord.id == decision_id).first()
        if not decision:
            raise HTTPException(status_code=404, detail="Decision not found")

        if body.title is not None:
            decision.title = body.title
        if body.description is not None:
            decision.description = body.description
        if body.decision_type is not None:
            decision.decision_type = body.decision_type
        if body.status is not None:
            decision.status = body.status
        if body.context_summary is not None:
            decision.context_summary = body.context_summary
        if body.alternatives_considered is not None:
            decision.alternatives_considered = body.alternatives_considered
        if body.outcome_summary is not None:
            decision.outcome_summary = body.outcome_summary
        if body.tags is not None:
            decision.tags = body.tags
        if body.involved_member_ids is not None:
            decision.involved_member_ids = body.involved_member_ids

        decision.updated_at = datetime.now(UTC)
        db.commit()

        # Refresh to get updated values
        db.refresh(decision)
        return _serialize_decision(decision)
    finally:
        db.close()


@router.post("/{decision_id}/link")
async def link_decisions(
    decision_id: str,
    body: LinkRequest,
    request: Request,
    user=Depends(get_current_user),
):
    """Link two decisions together."""
    valid_link_types = {"related", "supersedes", "depends_on", "contradicts"}
    if body.link_type not in valid_link_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid link type. Must be one of: {', '.join(valid_link_types)}",
        )

    db = _get_db()
    try:
        from_decision = db.query(DecisionRecord).filter(DecisionRecord.id == decision_id).first()
        if not from_decision:
            raise HTTPException(status_code=404, detail="Source decision not found")

        to_decision = db.query(DecisionRecord).filter(DecisionRecord.id == body.to_decision_id).first()
        if not to_decision:
            raise HTTPException(status_code=404, detail="Target decision not found")

        if decision_id == body.to_decision_id:
            raise HTTPException(status_code=400, detail="Cannot link a decision to itself")

        # Check for existing link
        existing = (
            db.query(DecisionLink)
            .filter(
                DecisionLink.from_decision_id == decision_id,
                DecisionLink.to_decision_id == body.to_decision_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Link already exists between these decisions")

        link_id = str(uuid.uuid4())
        link = DecisionLink(
            id=link_id,
            from_decision_id=decision_id,
            to_decision_id=body.to_decision_id,
            link_type=body.link_type,
            created_at=datetime.now(UTC),
        )
        db.add(link)
        db.commit()

        return {
            "id": link_id,
            "from_decision_id": decision_id,
            "to_decision_id": body.to_decision_id,
            "link_type": body.link_type,
            "created_at": link.created_at.isoformat(),
        }
    finally:
        db.close()


@router.delete("/{decision_id}")
async def delete_decision(
    decision_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    """Delete a decision and its links."""
    db = _get_db()
    try:
        decision = db.query(DecisionRecord).filter(DecisionRecord.id == decision_id).first()
        if not decision:
            raise HTTPException(status_code=404, detail="Decision not found")

        # Delete associated links (both directions)
        from sqlalchemy import or_

        db.query(DecisionLink).filter(
            or_(
                DecisionLink.from_decision_id == decision_id,
                DecisionLink.to_decision_id == decision_id,
            )
        ).delete(synchronize_session="fetch")

        db.delete(decision)
        db.commit()

        return {"status": "deleted", "decision_id": decision_id}
    finally:
        db.close()


@router.post("/{decision_id}/acknowledge")
async def acknowledge_decision(
    decision_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    """Acknowledge a decision (mark as reviewed by a human)."""
    db = _get_db()
    try:
        decision = db.query(DecisionRecord).filter(DecisionRecord.id == decision_id).first()
        if not decision:
            raise HTTPException(status_code=404, detail="Decision not found")

        decision.status = "active"
        decision.updated_at = datetime.now(UTC)
        db.commit()

        return {
            "id": decision_id,
            "status": "acknowledged",
            "acknowledged_by": user.id,
            "acknowledged_at": datetime.now(UTC).isoformat(),
        }
    finally:
        db.close()


# ── Helpers ─────────────────────────────────────────────────────────────────


# ── Decision Outcome Tracking ──


class RecordOutcomeRequest(BaseModel):
    outcome_description: str
    outcome_status: str = "positive"  # positive, negative, mixed, unknown
    lessons_learned: list[str] = []
    measured_at: str | None = None


@router.post("/{decision_id}/outcome")
async def record_decision_outcome(decision_id: str, body: RecordOutcomeRequest, user=Depends(get_current_user)):
    """Record the outcome of a decision — did it work?"""
    db = _get_db()
    try:
        decision = db.query(DecisionRecord).filter(DecisionRecord.id == decision_id).first()
        if not decision:
            raise HTTPException(404, "Decision not found")

        # Save outcome
        from app.models.decision import DecisionOutcome

        outcome = DecisionOutcome(
            id=str(uuid.uuid4()),
            decision_id=decision_id,
            outcome_description=body.outcome_description,
            outcome_status=body.outcome_status,
            lessons_learned=body.lessons_learned,
            recorded_by=user.id,
            recorded_at=datetime.now(UTC),
        )
        db.add(outcome)

        # Update decision's outcome_summary
        decision.outcome_summary = body.outcome_description
        decision.updated_at = datetime.now(UTC)
        db.commit()

        return {"status": "recorded", "outcome_id": outcome.id, "decision_id": decision_id}
    finally:
        db.close()


@router.get("/{decision_id}/outcomes")
async def get_decision_outcomes(decision_id: str, user=Depends(get_current_user)):
    """Get all recorded outcomes for a decision."""
    db = _get_db()
    try:
        from app.models.decision import DecisionOutcome

        outcomes = (
            db.query(DecisionOutcome)
            .filter(DecisionOutcome.decision_id == decision_id)
            .order_by(DecisionOutcome.recorded_at.desc())
            .all()
        )
        return {
            "decision_id": decision_id,
            "outcomes": [
                {
                    "id": o.id,
                    "outcome_description": o.outcome_description,
                    "outcome_status": o.outcome_status,
                    "lessons_learned": o.lessons_learned or [],
                    "recorded_by": o.recorded_by,
                    "recorded_at": o.recorded_at.isoformat() if o.recorded_at else None,
                }
                for o in outcomes
            ],
        }
    finally:
        db.close()


# ── Helpers ─────────────────────────────────────────────────────────────────


def _serialize_decision(decision: DecisionRecord) -> dict:
    """Convert a DecisionRecord to a serializable dict."""
    return {
        "id": decision.id,
        "organization_id": decision.organization_id,
        "title": decision.title,
        "description": decision.description,
        "decision_type": decision.decision_type,
        "status": decision.status,
        "confidence_score": decision.confidence_score,
        "context_summary": decision.context_summary,
        "alternatives_considered": decision.alternatives_considered or [],
        "outcome_summary": decision.outcome_summary,
        "source_artifact_ids": decision.source_artifact_ids or [],
        "source_chunk_ids": decision.source_chunk_ids or [],
        "involved_member_ids": decision.involved_member_ids or [],
        "tags": decision.tags or [],
        "decided_at": decision.decided_at.isoformat() if decision.decided_at else None,
        "extracted_at": decision.extracted_at.isoformat() if decision.extracted_at else None,
        "created_at": decision.created_at.isoformat() if decision.created_at else None,
        "updated_at": decision.updated_at.isoformat() if decision.updated_at else None,
    }
