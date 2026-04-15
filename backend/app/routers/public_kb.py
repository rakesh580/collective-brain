"""Public Knowledge Base router — unauthenticated read-only access to published content.

Artifacts and insights can be individually published (is_public=True).
These endpoints require NO authentication and are mounted at /public/.
"""
import logging

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.db.database import create_session
from app.models.artifact import ArtifactRecord
from app.models.insight import InsightRecord

logger = logging.getLogger("collective_brain.routers.public_kb")

# ── Authenticated management router (publish/unpublish) ───────────────────────
manage_router = APIRouter()

# ── Public read-only router (no auth) ─────────────────────────────────────────
public_router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class PublicArtifactResponse(BaseModel):
    id: str
    title: str | None
    source_type: str
    source_url: str | None
    ingested_at: str


class PublicInsightResponse(BaseModel):
    id: str
    title: str | None
    body: str | None
    insight_type: str | None
    generated_at: str
    confidence: float | None


class PublishResponse(BaseModel):
    id: str
    is_public: bool
    message: str


def _require_admin(request: Request):
    from app.dependencies import get_current_user
    user = get_current_user(request)
    if getattr(user, "role", "member") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Admin role required to publish content")
    return user


# ── Management endpoints (authenticated) ──────────────────────────────────────

@manage_router.post(
    "/artifacts/{artifact_id}/publish",
    response_model=PublishResponse,
    summary="Publish an artifact to the public knowledge base",
)
def publish_artifact(artifact_id: str, request: Request):
    _require_admin(request)
    db = create_session()
    try:
        artifact = db.query(ArtifactRecord).filter(ArtifactRecord.id == artifact_id).first()
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        artifact.is_public = True
        db.commit()
    finally:
        db.close()
    return PublishResponse(id=artifact_id, is_public=True, message="Artifact published successfully")


@manage_router.delete(
    "/artifacts/{artifact_id}/publish",
    response_model=PublishResponse,
    summary="Unpublish an artifact from the public knowledge base",
)
def unpublish_artifact(artifact_id: str, request: Request):
    _require_admin(request)
    db = create_session()
    try:
        artifact = db.query(ArtifactRecord).filter(ArtifactRecord.id == artifact_id).first()
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        artifact.is_public = False
        db.commit()
    finally:
        db.close()
    return PublishResponse(id=artifact_id, is_public=False, message="Artifact unpublished")


@manage_router.post(
    "/insights/{insight_id}/publish",
    response_model=PublishResponse,
    summary="Publish an insight to the public knowledge base",
)
def publish_insight(insight_id: str, request: Request):
    _require_admin(request)
    db = create_session()
    try:
        insight = db.query(InsightRecord).filter(InsightRecord.id == insight_id).first()
        if insight is None:
            raise HTTPException(status_code=404, detail="Insight not found")
        insight.is_public = True
        db.commit()
    finally:
        db.close()
    return PublishResponse(id=insight_id, is_public=True, message="Insight published successfully")


@manage_router.delete(
    "/insights/{insight_id}/publish",
    response_model=PublishResponse,
    summary="Unpublish an insight from the public knowledge base",
)
def unpublish_insight(insight_id: str, request: Request):
    _require_admin(request)
    db = create_session()
    try:
        insight = db.query(InsightRecord).filter(InsightRecord.id == insight_id).first()
        if insight is None:
            raise HTTPException(status_code=404, detail="Insight not found")
        insight.is_public = False
        db.commit()
    finally:
        db.close()
    return PublishResponse(id=insight_id, is_public=False, message="Insight unpublished")


# ── Public read-only endpoints (no auth) ──────────────────────────────────────

@public_router.get(
    "/artifacts",
    response_model=list[PublicArtifactResponse],
    summary="List publicly available artifacts",
)
def list_public_artifacts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    source_type: str | None = Query(default=None),
):
    db = create_session()
    try:
        q = db.query(ArtifactRecord).filter(ArtifactRecord.is_public.is_(True))
        if source_type:
            q = q.filter(ArtifactRecord.source_type == source_type)
        artifacts = q.order_by(ArtifactRecord.ingested_at.desc()).offset(offset).limit(limit).all()
        return [
            PublicArtifactResponse(
                id=a.id,
                title=a.title,
                source_type=a.source_type,
                source_url=getattr(a, "source_url", None),
                ingested_at=a.ingested_at.isoformat() if a.ingested_at else "",
            )
            for a in artifacts
        ]
    finally:
        db.close()


@public_router.get(
    "/artifacts/{artifact_id}",
    response_model=PublicArtifactResponse,
    summary="Get a single public artifact",
)
def get_public_artifact(artifact_id: str):
    db = create_session()
    try:
        artifact = (
            db.query(ArtifactRecord)
            .filter(ArtifactRecord.id == artifact_id, ArtifactRecord.is_public.is_(True))
            .first()
        )
    finally:
        db.close()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found or not public")
    return PublicArtifactResponse(
        id=artifact.id,
        title=artifact.title,
        source_type=artifact.source_type,
        source_url=getattr(artifact, "source_url", None),
        ingested_at=artifact.ingested_at.isoformat() if artifact.ingested_at else "",
    )


@public_router.get(
    "/insights",
    response_model=list[PublicInsightResponse],
    summary="List publicly available insights",
)
def list_public_insights(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    insight_type: str | None = Query(default=None),
):
    db = create_session()
    try:
        q = db.query(InsightRecord).filter(InsightRecord.is_public.is_(True))
        if insight_type:
            q = q.filter(InsightRecord.insight_type == insight_type)
        insights = q.order_by(InsightRecord.generated_at.desc()).offset(offset).limit(limit).all()
        return [
            PublicInsightResponse(
                id=i.id,
                title=i.title,
                body=i.body,
                insight_type=i.insight_type,
                generated_at=i.generated_at.isoformat() if i.generated_at else "",
                confidence=i.confidence,
            )
            for i in insights
        ]
    finally:
        db.close()


@public_router.get(
    "/insights/{insight_id}",
    response_model=PublicInsightResponse,
    summary="Get a single public insight",
)
def get_public_insight(insight_id: str):
    db = create_session()
    try:
        insight = (
            db.query(InsightRecord)
            .filter(InsightRecord.id == insight_id, InsightRecord.is_public.is_(True))
            .first()
        )
    finally:
        db.close()
    if insight is None:
        raise HTTPException(status_code=404, detail="Insight not found or not public")
    return PublicInsightResponse(
        id=insight.id,
        title=insight.title,
        body=insight.body,
        insight_type=insight.insight_type,
        generated_at=insight.generated_at.isoformat() if insight.generated_at else "",
        confidence=insight.confidence,
    )
