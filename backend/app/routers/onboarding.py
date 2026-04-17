"""Onboarding router — generate onboarding briefings for new team members."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.db.database import create_session
from app.dependencies import get_current_user

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
    """Generates a topic-specific briefing."""
    from app.services.onboarding_service import OnboardingService

    llm = request.app.state.llm_service
    svc = OnboardingService(llm)
    db = _get_db()
    try:
        result = await svc.generate_topic_briefing(db=db, topic=body.topic)
        return result
    finally:
        db.close()
