from datetime import datetime, timedelta
from fastapi import APIRouter, Request

from app.schemas.responses import (
    DashboardResponse,
    WeeklySummaryResponse,
    InsightResponse,
    MemberResponse,
)
from app.models.member import MemberRecord
from app.models.artifact import ArtifactRecord
from app.models.insight import InsightRecord
from app.services.insight_engine import InsightEngine
from app.db.database import get_session

router = APIRouter()


def _get_db():
    return next(get_session())


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(request: Request, room_id: str | None = None):
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        # Count total members (separate from top-10 query)
        total_members = db.query(MemberRecord).count()
        members = db.query(MemberRecord).order_by(MemberRecord.total_contributions.desc()).limit(10).all()

        art_query = db.query(ArtifactRecord)
        if room_id:
            art_query = art_query.filter(ArtifactRecord.room_id == room_id)
        total_artifacts = art_query.count()

        ins_query = (
            db.query(InsightRecord)
            .order_by(InsightRecord.generated_at.desc())
        )
        if room_id:
            ins_query = ins_query.filter(InsightRecord.room_id == room_id)
        insights = ins_query.limit(5).all()
        vs = request.app.state.vector_store

        return DashboardResponse(
            total_members=total_members,
            total_artifacts=total_artifacts,
            total_chunks=vs.count(),
            top_insights=[
                InsightResponse(
                    id=i.id,
                    insight_type=i.insight_type or "",
                    title=i.title or "",
                    body=i.body or "",
                    generated_at=i.generated_at,
                    related_member_ids=i.related_member_ids or [],
                    confidence=i.confidence or 0,
                )
                for i in insights
            ],
            active_members=[
                MemberResponse(
                    id=m.id,
                    name=m.name,
                    aliases=m.aliases or [],
                    email=m.email,
                    expertise_tags=m.expertise_tags or [],
                    expertise_scores=m.expertise_scores or {},
                    strengths=m.strengths or [],
                    weaknesses=m.weaknesses or [],
                    last_active=m.last_active,
                    total_contributions=m.total_contributions or 0,
                )
                for m in members
            ],
        )
    finally:
        db.close()


@router.get("/weekly", response_model=WeeklySummaryResponse)
async def get_weekly_summary(request: Request, room_id: str | None = None):
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        # Check for cached weekly summary
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        cache_query = (
            db.query(InsightRecord)
            .filter(
                InsightRecord.insight_type == "weekly_summary",
                InsightRecord.period_end >= week_ago,
            )
        )
        if room_id:
            cache_query = cache_query.filter(InsightRecord.room_id == room_id)
        cached = cache_query.order_by(InsightRecord.generated_at.desc()).first()

        if cached:
            meta = cached.metadata_json or {}
            return WeeklySummaryResponse(
                summary=cached.body or "",
                period_start=cached.period_start or week_ago,
                period_end=cached.period_end or now,
                highlights=meta.get("highlights", []),
                recommendations=meta.get("recommendations", []),
            )

        # Generate new
        engine = InsightEngine(db, request.app.state.llm_service, room_id=room_id)
        insight = await engine.generate_weekly_summary()
        meta = insight.metadata_json or {}
        return WeeklySummaryResponse(
            summary=insight.body or "",
            period_start=insight.period_start or week_ago,
            period_end=insight.period_end or now,
            highlights=meta.get("highlights", []),
            recommendations=meta.get("recommendations", []),
        )
    finally:
        db.close()


@router.get("/patterns", response_model=list[InsightResponse])
async def get_patterns(request: Request, room_id: str | None = None):
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        engine = InsightEngine(db, request.app.state.llm_service, room_id=room_id)
        insights = await engine.get_cached_insights(limit=20)
        if not insights:
            insights = await engine.detect_patterns()

        return [
            InsightResponse(
                id=i.id,
                insight_type=i.insight_type or "",
                title=i.title or "",
                body=i.body or "",
                generated_at=i.generated_at,
                related_member_ids=i.related_member_ids or [],
                confidence=i.confidence or 0,
            )
            for i in insights
        ]
    finally:
        db.close()


@router.post("/generate", response_model=list[InsightResponse])
async def generate_insights(request: Request, room_id: str | None = None):
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        engine = InsightEngine(db, request.app.state.llm_service, room_id=room_id)
        insights = await engine.detect_patterns()
        return [
            InsightResponse(
                id=i.id,
                insight_type=i.insight_type or "",
                title=i.title or "",
                body=i.body or "",
                generated_at=i.generated_at,
                related_member_ids=i.related_member_ids or [],
                confidence=i.confidence or 0,
            )
            for i in insights
        ]
    finally:
        db.close()
