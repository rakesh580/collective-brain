"""Notification Service — sends risk alerts and decision notifications via webhooks."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.decision import NotificationLog
from app.models.decision import NotificationWebhook as WebhookRegistration

logger = logging.getLogger("collective_brain.notifications")


class NotificationService:
    """Manages notifications for risk alerts and decisions."""

    def __init__(self):
        self.logger = logging.getLogger("collective_brain.notifications")

    # ------------------------------------------------------------------
    # Webhook management
    # ------------------------------------------------------------------

    def register_webhook(self, db: Session, url: str, event_types: list[str]) -> dict:
        """Register a webhook URL for notifications."""
        webhook_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        registration = WebhookRegistration(
            id=webhook_id,
            url=url,
            event_types=event_types,
            is_active=True,
            created_at=now,
        )
        db.add(registration)

        try:
            db.commit()
            self.logger.info("Registered webhook %s for events %s", webhook_id, event_types)
        except Exception:
            db.rollback()
            self.logger.exception("Failed to register webhook")
            raise

        return {
            "id": webhook_id,
            "url": url,
            "event_types": event_types,
            "is_active": True,
            "created_at": now.isoformat(),
        }

    def unregister_webhook(self, db: Session, webhook_id: str) -> bool:
        """Remove a webhook registration."""
        registration = (
            db.query(WebhookRegistration)
            .filter(WebhookRegistration.id == webhook_id)
            .first()
        )
        if not registration:
            return False

        db.delete(registration)
        try:
            db.commit()
            self.logger.info("Unregistered webhook %s", webhook_id)
        except Exception:
            db.rollback()
            self.logger.exception("Failed to unregister webhook %s", webhook_id)
            raise

        return True

    def get_webhooks(self, db: Session) -> list[dict]:
        """List all registered webhooks."""
        registrations = (
            db.query(WebhookRegistration)
            .filter(WebhookRegistration.is_active == True)  # noqa: E712
            .order_by(WebhookRegistration.created_at.desc())
            .all()
        )

        return [
            {
                "id": r.id,
                "url": r.url,
                "event_types": r.event_types if isinstance(r.event_types, list) else [],
                "is_active": bool(r.is_active),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in registrations
        ]

    # ------------------------------------------------------------------
    # Notification dispatch
    # ------------------------------------------------------------------

    async def notify_risk_alert(self, db: Session, alert: dict) -> dict:
        """Send notification for a new risk alert.

        Sends to all registered webhooks with event_type 'risk_alert'.
        Returns delivery status.
        """
        payload = {
            "event_type": "risk_alert",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": alert,
        }

        return await self._dispatch_to_webhooks(db, "risk_alert", payload)

    async def notify_decision_extracted(self, db: Session, decisions: list[dict]) -> dict:
        """Notify when new decisions are extracted."""
        payload = {
            "event_type": "decision_extracted",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "decision_count": len(decisions),
                "decisions": decisions,
            },
        }

        return await self._dispatch_to_webhooks(db, "decision_extracted", payload)

    def get_notification_history(self, db: Session, limit: int = 50) -> list[dict]:
        """Get recent notification delivery history."""
        logs = (
            db.query(NotificationLog)
            .order_by(NotificationLog.sent_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": log.id,
                "webhook_id": log.webhook_id,
                "event_type": log.event_type,
                "success": bool(log.success),
                "error_message": log.error_message,
                "sent_at": log.sent_at.isoformat() if log.sent_at else None,
            }
            for log in logs
        ]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _dispatch_to_webhooks(
        self,
        db: Session,
        event_type: str,
        payload: dict,
    ) -> dict:
        """Dispatch payload to all webhooks registered for the given event type."""
        webhooks = (
            db.query(WebhookRegistration)
            .filter(WebhookRegistration.is_active == True)  # noqa: E712
            .all()
        )

        # Filter to webhooks that listen for this event type
        matching = []
        for wh in webhooks:
            event_types = wh.event_types if isinstance(wh.event_types, list) else []
            if event_type in event_types or "*" in event_types:
                matching.append(wh)

        if not matching:
            self.logger.info("No webhooks registered for event_type=%s", event_type)
            return {
                "event_type": event_type,
                "webhooks_notified": 0,
                "successes": 0,
                "failures": 0,
                "details": [],
            }

        successes = 0
        failures = 0
        details: list[dict] = []

        for wh in matching:
            success = await self._send_webhook(wh.url, payload)

            # Log delivery
            log_id = str(uuid.uuid4())
            error_msg = None if success else f"Delivery failed to {wh.url}"
            log_entry = NotificationLog(
                id=log_id,
                webhook_id=wh.id,
                event_type=event_type,
                payload_summary=str(payload.get("event_type", ""))[:200],
                success=success,
                error_message=error_msg,
                sent_at=datetime.now(UTC),
            )
            db.add(log_entry)

            if success:
                successes += 1
            else:
                failures += 1

            details.append({
                "webhook_id": wh.id,
                "url": wh.url,
                "success": success,
                "error_message": error_msg,
            })

        try:
            db.commit()
        except Exception:
            db.rollback()
            self.logger.exception("Failed to save notification logs")

        self.logger.info(
            "Dispatched %s to %d webhook(s): %d success, %d failed",
            event_type,
            len(matching),
            successes,
            failures,
        )

        return {
            "event_type": event_type,
            "webhooks_notified": len(matching),
            "successes": successes,
            "failures": failures,
            "details": details,
        }

    async def _send_webhook(self, url: str, payload: dict) -> bool:
        """Send a single webhook POST request."""
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session, session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"Content-Type": "application/json"},
            ) as resp:
                success = resp.status < 400
                if not success:
                    self.logger.warning(
                        "Webhook delivery to %s returned status %d",
                        url,
                        resp.status,
                    )
                return success
        except aiohttp.ClientError as e:
            self.logger.error("Webhook delivery failed to %s: %s", url, e)
            return False
        except Exception as e:
            self.logger.error("Unexpected error sending webhook to %s: %s", url, e)
            return False
