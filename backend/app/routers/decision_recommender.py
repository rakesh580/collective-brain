"""Decision Recommender router — "Who should decide this?" feature."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.db.database import create_session
from app.dependencies import get_current_user

router = APIRouter()


def _get_db():
    return create_session()


class RecommendRequest(BaseModel):
    topic: str
    decision_type: str = "technical"
    top_k: int = 5


@router.post("/recommend")
async def recommend_decision_makers(
    body: RecommendRequest,
    user=Depends(get_current_user),
):
    """Returns recommended decision makers with scores and reasons."""
    from app.services.decision_recommender import DecisionRecommenderService

    svc = DecisionRecommenderService()
    db = _get_db()
    try:
        return svc.recommend_decision_makers(
            db=db,
            topic=body.topic,
            decision_type=body.decision_type,
            top_k=body.top_k,
        )
    finally:
        db.close()


@router.get("/influence-map")
async def get_influence_map(
    user=Depends(get_current_user),
):
    """Returns decision influence distribution."""
    from app.services.decision_recommender import DecisionRecommenderService

    svc = DecisionRecommenderService()
    db = _get_db()
    try:
        return svc.get_decision_influence_map(db)
    finally:
        db.close()
