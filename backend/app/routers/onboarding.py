"""Onboarding router — generate onboarding briefings for new team members."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.db.database import create_session
from app.dependencies import get_current_user

logger = logging.getLogger("collective_brain.onboarding")

router = APIRouter()


def _get_db():
    return create_session()


class BriefingRequest(BaseModel):
    member_id: str | None = None
    topics: list[str] | None = None


class TopicBriefingRequest(BaseModel):
    topic: str


@router.post("/briefing")
async def generate_briefing(
    body: BriefingRequest,
    request: Request,
    user=Depends(get_current_user),
):
    """Generates a comprehensive onboarding briefing using LLM."""
    from app.services.onboarding_service import OnboardingService

    llm = request.app.state.llm_service
    svc = OnboardingService(llm)
    db = _get_db()
    try:
        result = await svc.generate_briefing(
            db=db,
            member_id=body.member_id,
            topics=body.topics,
        )
        return result
    finally:
        db.close()


@router.post("/topic-briefing")
async def generate_topic_briefing(
    body: TopicBriefingRequest,
    request: Request,
    user=Depends(get_current_user),
):
    """Generates a topic-specific briefing.

    Graceful-degradation: if the underlying service raises (LLM
    unavailable, DB column missing on a stale deployment, empty
    result-set in a not-yet-ingested workspace), we return a
    well-typed empty-state body so the UI renders an "nothing yet"
    panel instead of crashing with a 500. The exception is logged so
    observability still catches real problems.
    """
    from app.services.onboarding_service import OnboardingService

    llm = request.app.state.llm_service
    svc = OnboardingService(llm)
    db = _get_db()
    try:
        return await svc.generate_topic_briefing(db=db, topic=body.topic)
    except Exception:
        logger.exception(
            "topic_briefing failed for topic=%r — returning empty-state body",
            body.topic,
        )
        return {
            "topic": body.topic,
            "generated_at": datetime.now(UTC).isoformat(),
            "decisions": [],
            "members": [],
            "artifacts": [],
            "knowledge_chunk_count": 0,
            "summary": (
                f"No briefing data is available for '{body.topic}' yet. "
                "This is normal for a freshly-deployed workspace. Once your "
                "GitHub/Slack integrations have ingested data and migrations "
                "are at head, this page will populate automatically."
            ),
        }
    finally:
        db.close()
