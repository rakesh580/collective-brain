from fastapi import APIRouter, HTTPException, Request

from app.models.artifact import ArtifactRecord
from app.models.contribution import ContributionRecord
from app.db.database import get_session

router = APIRouter()


def _get_db():
    return next(get_session())


@router.get("")
async def list_artifacts(
    request: Request,
    source_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        query = db.query(ArtifactRecord)
        if source_type:
            query = query.filter(ArtifactRecord.source_type == source_type)
        total = query.count()
        artifacts = (
            query.order_by(ArtifactRecord.ingested_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "artifacts": [
                {
                    "id": a.id,
                    "source_type": a.source_type,
                    "source_path": a.source_path,
                    "title": a.title,
                    "ingested_at": a.ingested_at.isoformat() if a.ingested_at else None,
                    "chunk_count": a.chunk_count or 0,
                    "member_ids": a.member_ids or [],
                    "status": a.status,
                }
                for a in artifacts
            ],
            "total": total,
        }
    finally:
        db.close()


@router.get("/{artifact_id}")
async def get_artifact(artifact_id: str, request: Request):
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        artifact = (
            db.query(ArtifactRecord)
            .filter(ArtifactRecord.id == artifact_id)
            .first()
        )
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return {
            "id": artifact.id,
            "source_type": artifact.source_type,
            "source_path": artifact.source_path,
            "title": artifact.title,
            "ingested_at": artifact.ingested_at.isoformat() if artifact.ingested_at else None,
            "chunk_count": artifact.chunk_count or 0,
            "member_ids": artifact.member_ids or [],
            "status": artifact.status,
        }
    finally:
        db.close()


@router.delete("/{artifact_id}")
async def delete_artifact(artifact_id: str, request: Request):
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        artifact = (
            db.query(ArtifactRecord)
            .filter(ArtifactRecord.id == artifact_id)
            .first()
        )
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")

        # Delete contributions linked to this artifact
        db.query(ContributionRecord).filter(
            ContributionRecord.artifact_id == artifact_id
        ).delete()

        # Delete vector chunks for this artifact
        vs = request.app.state.vector_store
        vs.delete_by_artifact(artifact_id)

        db.delete(artifact)
        db.commit()
        return {"status": "deleted", "artifact_id": artifact_id}
    finally:
        db.close()
