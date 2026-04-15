from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.db.database import create_session
from app.dependencies import get_current_user
from app.models.artifact import ArtifactRecord
from app.models.insight import InsightRecord
from app.models.member import MemberRecord
from app.schemas.responses import (
    DashboardResponse,
    InsightResponse,
    MemberResponse,
    WeeklySummaryResponse,
)
from app.services.freshness_service import get_freshness_report
from app.services.insight_engine import InsightEngine
from app.services.knowledge_verification import KnowledgeVerificationService

router = APIRouter()


# ── Verification schemas ───────────────────────────────────────────────────────


class VerifyInsightRequest(BaseModel):
    run_llm_spot_check: bool = False


class VerifyInsightResponse(BaseModel):
    insight_id: str
    status: str
    staleness_days: int | None
    reasons: list[str]
    spot_check_summary: str | None = None


class BulkVerifyResponse(BaseModel):
    verified: int = 0
    outdated: int = 0
    disputed: int = 0


def _get_db():
    return create_session()


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(request: Request, room_id: str | None = None, user=Depends(get_current_user)):
    db = _get_db()
    try:
        # Count total members (separate from top-10 query)
        total_members = db.query(MemberRecord).count()
        members = db.query(MemberRecord).order_by(MemberRecord.total_contributions.desc()).limit(10).all()

        art_query = db.query(ArtifactRecord)
        if room_id:
            art_query = art_query.filter(ArtifactRecord.room_id == room_id)
        total_artifacts = art_query.count()

        ins_query = db.query(InsightRecord).order_by(InsightRecord.generated_at.desc())
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
async def get_weekly_summary(request: Request, room_id: str | None = None, user=Depends(get_current_user)):
    db = _get_db()
    try:
        # Check for cached weekly summary
        now = datetime.now(UTC)
        week_ago = now - timedelta(days=7)
        cache_query = db.query(InsightRecord).filter(
            InsightRecord.insight_type == "weekly_summary",
            InsightRecord.period_end >= week_ago,
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
        try:
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
        except Exception:
            # LLM unavailable — return empty summary
            return WeeklySummaryResponse(
                summary="Weekly summary is unavailable. Please configure an LLM provider.",
                period_start=week_ago,
                period_end=now,
                highlights=[],
                recommendations=["Configure CB_MISTRAL_API_KEY or CB_CLAUDE_API_KEY to enable AI summaries."],
            )
    finally:
        db.close()


@router.get("/patterns", response_model=list[InsightResponse])
async def get_patterns(request: Request, room_id: str | None = None, user=Depends(get_current_user)):
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
async def generate_insights(request: Request, room_id: str | None = None, user=Depends(get_current_user)):
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


@router.get("/freshness")
async def freshness_report(request: Request, user=Depends(get_current_user)):
    """Return full freshness report for all artifacts."""
    db = _get_db()
    try:
        return get_freshness_report(db)
    finally:
        db.close()


@router.get("/freshness/alerts")
async def freshness_alerts(request: Request, user=Depends(get_current_user)):
    """Return top 10 stale/critical freshness alerts."""
    db = _get_db()
    try:
        report = get_freshness_report(db)
        # Return stale and aging alerts, prioritized by staleness score
        all_alerts = report["alerts"]
        critical_alerts = [a for a in all_alerts if a["status"] in ("stale", "aging")]
        return {"alerts": critical_alerts[:10]}
    finally:
        db.close()


# ── Knowledge Verification (Phase 5) ─────────────────────────────────────────


@router.post("/{insight_id}/verify", response_model=VerifyInsightResponse)
async def verify_insight(
    insight_id: str,
    body: VerifyInsightRequest,
    request: Request,
    user=Depends(get_current_user),
):
    """Run verification checks on a single insight."""
    db = _get_db()
    try:
        insight = db.query(InsightRecord).filter_by(id=insight_id).first()
        if not insight:
            raise HTTPException(status_code=404, detail="Insight not found")

        settings = request.app.state.settings
        svc = KnowledgeVerificationService(staleness_threshold_days=settings.knowledge_staleness_threshold_days)
        result = svc.verify_insight(
            db,
            insight,
            run_llm_spot_check=body.run_llm_spot_check,
            llm_service=request.app.state.llm_service if body.run_llm_spot_check else None,
            vector_store=request.app.state.vector_store if body.run_llm_spot_check else None,
            embedding_service=request.app.state.embedding_service if body.run_llm_spot_check else None,
            verifier_user_id=user.id,
        )
        return VerifyInsightResponse(
            insight_id=insight_id,
            status=result.status,
            staleness_days=result.staleness_days,
            reasons=result.reasons,
            spot_check_summary=result.spot_check_summary,
        )
    finally:
        db.close()


@router.post("/verify/bulk", response_model=BulkVerifyResponse)
async def bulk_verify_insights(
    request: Request,
    organization_id: str | None = None,
    limit: int = 100,
    user=Depends(get_current_user),
):
    """Run staleness verification on all pending/outdated insights (no LLM)."""
    db = _get_db()
    try:
        settings = request.app.state.settings
        svc = KnowledgeVerificationService(staleness_threshold_days=settings.knowledge_staleness_threshold_days)
        summary = svc.bulk_verify(db, organization_id=organization_id, limit=limit)
        return BulkVerifyResponse(**summary)
    finally:
        db.close()


@router.get("/verification-status")
async def list_insights_by_verification(
    request: Request,
    status: str = "pending",
    limit: int = 50,
    user=Depends(get_current_user),
):
    """List insights filtered by verification_status."""
    allowed = {"pending", "verified", "outdated", "disputed"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail=f"status must be one of {allowed}")
    db = _get_db()
    try:
        insights = (
            db.query(InsightRecord)
            .filter(InsightRecord.verification_status == status)
            .order_by(InsightRecord.generated_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": i.id,
                "title": i.title,
                "insight_type": i.insight_type,
                "verification_status": i.verification_status,
                "staleness_days": i.staleness_days,
                "verified_at": i.verified_at,
                "confidence": i.confidence,
            }
            for i in insights
        ]
    finally:
        db.close()
