"""Notifications router — webhook notification management."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db.database import create_session
from app.dependencies import get_current_user
from app.services.notification_service import NotificationService

router = APIRouter()

_service = NotificationService()


def _get_db():
    return create_session()


class WebhookCreateRequest(BaseModel):
    url: str
    event_types: list[str]


@router.post("/webhooks")
async def register_webhook(
    body: WebhookCreateRequest,
    user=Depends(get_current_user),
):
    """Register a new webhook."""
    db = _get_db()
    try:
        return _service.register_webhook(db, url=body.url, event_types=body.event_types)
    finally:
        db.close()


@router.get("/webhooks")
async def list_webhooks(
    user=Depends(get_current_user),
):
    """List all active webhooks."""
    db = _get_db()
    try:
        webhooks = _service.get_webhooks(db)
        return {"webhooks": webhooks}
    finally:
        db.close()


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    user=Depends(get_current_user),
):
    """Remove a webhook."""
    db = _get_db()
    try:
        deleted = _service.unregister_webhook(db, webhook_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Webhook not found")
        return {"status": "deleted", "webhook_id": webhook_id}
    finally:
        db.close()


@router.get("/history")
async def get_notification_history(
    limit: int = 50,
    user=Depends(get_current_user),
):
    """Get notification delivery history."""
    db = _get_db()
    try:
        notifications = _service.get_notification_history(db, limit=limit)
        return {"notifications": notifications}
    finally:
        db.close()
