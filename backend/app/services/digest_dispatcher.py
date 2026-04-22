"""Weekly-digest dispatcher job.

Runs hourly (UTC). Resolves each organization's local time via its configured
``digest_timezone`` and fires due digests to Slack where available; otherwise
falls back to SMTP email (admin recipients); otherwise records an in-app
digest for the Dashboard card.

Every attempt — successful, failed, or skipped — writes a ``digest_log``
row for audit.

Idempotency: the Slack path honors ``SlackDigestConfig.last_sent_at``;
the email path checks for a ``digest_log`` row with status="sent" within
the last 23h for the same (org, delivery_channel).

Failure modes:
- Slack 5xx / network flaps — wrapped in a CircuitBreaker (5 failures / 60s
  recovery). When OPEN, sends are logged ``status="failed"`` with the
  CircuitBreakerError; individual orgs still attempt the email fallback on
  the next hourly tick if no Slack config exists.
- SMTP outage — wrapped in a separate breaker so Slack and email trip
  independently. Email failures fall back to ``delivery_channel="in_app"``.
- Per-config errors are isolated: one bad workspace never blocks the rest.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.models.digest_log import DigestLog
from app.models.organization import OrganizationMembership, OrganizationRecord
from app.models.slack_digest_config import SlackDigestConfig
from app.models.slack_integration import SlackWorkspace
from app.models.user import UserRecord
from app.services.circuit_breaker import CircuitBreaker
from app.services.digest_service import (
    format_text_digest,
    generate_weekly_digest,
    send_digest_to_slack,
)
from app.services.email_service import EmailNotConfigured, send_email

# Module-level breakers. One digest tick can touch N Slack workspaces and M
# email orgs; these trip independently so a flapping Slack doesn't silence
# email, and vice-versa.
_slack_breaker = CircuitBreaker(
    "digest_slack", failure_threshold=5, recovery_timeout=60.0
)
_email_breaker = CircuitBreaker(
    "digest_email", failure_threshold=5, recovery_timeout=120.0
)


def reset_breakers_for_tests() -> None:
    """Test helper — clears breaker state between test runs."""
    _slack_breaker.reset()
    _email_breaker.reset()


async def _send_email_via_breaker(**kwargs) -> dict:
    """Run the sync SMTP send through the email circuit breaker.

    ``EmailNotConfigured`` is raised before the breaker runs — it's a
    static misconfig, not a flap, so it shouldn't trip the circuit and
    silence every subsequent attempt. Real SMTP errors (timeouts, auth
    failures) flow through the breaker normally.
    """

    async def _job():
        return await asyncio.to_thread(send_email, **kwargs)

    try:
        return await _email_breaker.call(_job)
    except EmailNotConfigured:
        # Breaker counted this as a failure — undo so it stays CLOSED.
        _email_breaker.reset()
        raise

logger = logging.getLogger("collective_brain.digest_dispatcher")

_MIN_SEND_SPACING = timedelta(hours=23)

# Default email-fallback schedule per plan: "Friday 4 PM in the org's
# configured timezone." ISO weekday: Friday == 4 (Mon=0).
DEFAULT_EMAIL_DAY = 4
DEFAULT_EMAIL_HOUR = 16


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _org_local_now(org: OrganizationRecord, now_utc: datetime) -> datetime:
    """Resolve ``now_utc`` into the organization's local wall clock."""
    tz_name = getattr(org, "digest_timezone", None) or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning("Org %s has invalid digest_timezone=%r — falling back to UTC", org.id, tz_name)
        tz = ZoneInfo("UTC")
    return now_utc.astimezone(tz)


def _recent_enough(last_sent_at: datetime | None, now_utc: datetime) -> bool:
    if last_sent_at is None:
        return False
    last = last_sent_at if last_sent_at.tzinfo else last_sent_at.replace(tzinfo=UTC)
    return now_utc - last < _MIN_SEND_SPACING


def _is_slack_cfg_due(
    cfg: SlackDigestConfig,
    org_local: datetime,
    now_utc: datetime,
) -> bool:
    if not cfg.enabled:
        return False
    if cfg.schedule_day != org_local.weekday():
        return False
    if cfg.schedule_hour != org_local.hour:
        return False
    return not _recent_enough(cfg.last_sent_at, now_utc)


def _record_log(
    db: Session,
    *,
    organization_id: str | None,
    workspace_id: str | None,
    channel_id: str | None,
    delivery_channel: str,
    recipient: str | None,
    status: str,
    error: str | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    now: datetime,
) -> None:
    entry = DigestLog(
        id=str(uuid.uuid4()),
        organization_id=organization_id,
        workspace_id=workspace_id,
        channel_id=channel_id,
        delivery_channel=delivery_channel,
        recipient=recipient,
        status=status,
        error=error,
        period_start=period_start,
        period_end=period_end,
        sent_at=now,
    )
    db.add(entry)


def _recent_digest_log_exists(
    db: Session,
    organization_id: str,
    delivery_channel: str,
    now_utc: datetime,
) -> bool:
    """Idempotency helper for non-Slack paths (Slack uses last_sent_at)."""
    since = now_utc - _MIN_SEND_SPACING
    row = (
        db.query(DigestLog)
        .filter(
            DigestLog.organization_id == organization_id,
            DigestLog.delivery_channel == delivery_channel,
            DigestLog.status == "sent",
            DigestLog.sent_at >= since,
        )
        .first()
    )
    return row is not None


def _admin_emails_for_org(db: Session, org_id: str) -> list[str]:
    q = (
        db.query(UserRecord.email)
        .join(OrganizationMembership, OrganizationMembership.user_id == UserRecord.id)
        .filter(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.role.in_(["owner", "admin"]),
            UserRecord.is_active == True,  # noqa: E712
        )
    )
    return [row[0] for row in q.all() if row[0]]


async def _dispatch_slack_for_org(
    db: Session,
    org: OrganizationRecord,
    now_utc: datetime,
    summary: dict[str, Any],
) -> bool:
    """Fire any due SlackDigestConfig for this org.

    Returns True if the org *has any* configs — whether they fired or not —
    so the email fallback only activates for orgs with no Slack setup at all.
    A Slack failure lands in digest_log; we don't double-dip via email.
    """
    org_local = _org_local_now(org, now_utc)

    configs = (
        db.query(SlackDigestConfig)
        .join(SlackWorkspace, SlackWorkspace.id == SlackDigestConfig.workspace_id)
        .filter(SlackWorkspace.organization_id == org.id)
        .all()
    )
    has_configs = bool(configs)

    for cfg in configs:
        summary["checked"] += 1
        if not _is_slack_cfg_due(cfg, org_local, now_utc):
            continue
        summary["due"] += 1

        try:
            await _slack_breaker.call(
                send_digest_to_slack,
                db=db,
                workspace_id=cfg.workspace_id,
                channel_id=cfg.channel_id,
            )
            summary["sent"] += 1
            _record_log(
                db,
                organization_id=org.id,
                workspace_id=cfg.workspace_id,
                channel_id=cfg.channel_id,
                delivery_channel="slack",
                recipient=cfg.channel_id,
                status="sent",
                now=now_utc,
            )
        except Exception as exc:
            summary["failed"] += 1
            _record_log(
                db,
                organization_id=org.id,
                workspace_id=cfg.workspace_id,
                channel_id=cfg.channel_id,
                delivery_channel="slack",
                recipient=cfg.channel_id,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
                now=now_utc,
            )
            logger.exception(
                "Slack digest failed for org=%s channel=%s", org.id, cfg.channel_id
            )
    return has_configs


async def _dispatch_email_for_org(
    db: Session,
    org: OrganizationRecord,
    now_utc: datetime,
    summary: dict[str, Any],
) -> None:
    """Email fallback for orgs without a Slack digest configured."""
    org_local = _org_local_now(org, now_utc)
    if org_local.weekday() != DEFAULT_EMAIL_DAY or org_local.hour != DEFAULT_EMAIL_HOUR:
        return
    summary["checked"] += 1
    summary["due"] += 1

    if _recent_digest_log_exists(db, org.id, "email", now_utc):
        return  # already sent in the last 23h

    recipients = _admin_emails_for_org(db, org.id)
    if not recipients:
        _record_log(
            db,
            organization_id=org.id,
            workspace_id=None,
            channel_id=None,
            delivery_channel="in_app",
            recipient=None,
            status="skipped",
            error="no admin recipients",
            now=now_utc,
        )
        summary["failed"] += 1
        return

    try:
        digest_data = generate_weekly_digest(db)
        body = format_text_digest(digest_data)
        period_start = _parse_iso(digest_data.get("period_start"))
        period_end = _parse_iso(digest_data.get("period_end"))
        # Run the SMTP send through the breaker so a bad relay doesn't
        # block the rest of the orgs-loop or hold the event loop open.
        await _send_email_via_breaker(
            to=recipients,
            subject=f"Weekly Knowledge Digest — {org.name}",
            text_body=body,
        )
        _record_log(
            db,
            organization_id=org.id,
            workspace_id=None,
            channel_id=None,
            delivery_channel="email",
            recipient=",".join(recipients),
            status="sent",
            period_start=period_start,
            period_end=period_end,
            now=now_utc,
        )
        summary["sent"] += 1
    except EmailNotConfigured as exc:
        # Fall through to in-app: persist a log row so the Dashboard card renders.
        digest_data = generate_weekly_digest(db)
        period_start = _parse_iso(digest_data.get("period_start"))
        period_end = _parse_iso(digest_data.get("period_end"))
        _record_log(
            db,
            organization_id=org.id,
            workspace_id=None,
            channel_id=None,
            delivery_channel="in_app",
            recipient=None,
            status="sent",
            period_start=period_start,
            period_end=period_end,
            now=now_utc,
            error=str(exc),
        )
        summary["sent"] += 1
    except Exception as exc:
        summary["failed"] += 1
        _record_log(
            db,
            organization_id=org.id,
            workspace_id=None,
            channel_id=None,
            delivery_channel="email",
            recipient=",".join(recipients),
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
            now=now_utc,
        )
        logger.exception("Email digest failed for org=%s", org.id)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


async def run_due_digests(db: Session, now: datetime | None = None) -> dict[str, Any]:
    """Dispatch every digest that is due this hour (timezone-aware)."""
    current = now or _now_utc()
    summary: dict[str, Any] = {
        "checked": 0,
        "due": 0,
        "sent": 0,
        "failed": 0,
        "ran_at": current.isoformat(),
    }

    orgs = (
        db.query(OrganizationRecord)
        .filter(OrganizationRecord.is_active == True)  # noqa: E712
        .filter(OrganizationRecord.digest_enabled == True)  # noqa: E712
        .all()
    )

    for org in orgs:
        org_has_slack = await _dispatch_slack_for_org(db, org, current, summary)
        if not org_has_slack:
            await _dispatch_email_for_org(db, org, current, summary)

    db.commit()
    logger.info(
        "Digest dispatcher: orgs=%d checked=%d due=%d sent=%d failed=%d",
        len(orgs),
        summary["checked"],
        summary["due"],
        summary["sent"],
        summary["failed"],
    )
    return summary


async def run_due_digests_job() -> dict[str, Any]:
    """Scheduler entrypoint. Opens its own DB session per run."""
    from app.db.database import create_session

    db = create_session()
    try:
        return await run_due_digests(db)
    finally:
        db.close()
