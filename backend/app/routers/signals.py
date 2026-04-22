"""Signals API — list, acknowledge, resolve detected patterns."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.db.database import create_session
from app.dependencies import get_current_user
from app.models.signal import Signal

logger = logging.getLogger("collective_brain.routers.signals")
router = APIRouter()


def _get_db():
    return create_session()


def _serialize(s: Signal) -> dict:
    return {
        "id": s.id,
        "organization_id": s.organization_id,
        "signal_type": s.signal_type,
        "severity": s.severity,
        "title": s.title,
        "description": s.description,
        "evidence": s.evidence or {},
        "suggested_action": s.suggested_action,
        "dedup_key": s.dedup_key,
        "detected_at": s.detected_at.isoformat() if s.detected_at else None,
        "acknowledged_by": s.acknowledged_by,
        "acknowledged_at": s.acknowledged_at.isoformat() if s.acknowledged_at else None,
        "resolved_at": s.resolved_at.isoformat() if s.resolved_at else None,
    }


@router.get("")
async def list_signals(
    request: Request,
    status: str = Query(default="open", pattern="^(open|acknowledged|resolved|all)$"),
    limit: int = Query(default=50, ge=1, le=200),
    user=Depends(get_current_user),
):
    """List signals for the current user's org, filtered by lifecycle status."""
    db = _get_db()
    try:
        org_id = getattr(user, "organization_id", None)
        q = db.query(Signal)
        if org_id:
            q = q.filter(Signal.organization_id == org_id)

        if status == "open":
            q = q.filter(Signal.resolved_at.is_(None), Signal.acknowledged_at.is_(None))
        elif status == "acknowledged":
            q = q.filter(Signal.resolved_at.is_(None), Signal.acknowledged_at.isnot(None))
        elif status == "resolved":
            q = q.filter(Signal.resolved_at.isnot(None))
        # "all" → no filter

        rows = q.order_by(Signal.detected_at.desc()).limit(limit).all()
        return {"signals": [_serialize(r) for r in rows], "count": len(rows)}
    finally:
        db.close()


@router.post("/{signal_id}/acknowledge")
async def acknowledge_signal(signal_id: str, request: Request, user=Depends(get_current_user)):
    db = _get_db()
    try:
        signal = db.query(Signal).filter(Signal.id == signal_id).first()
        if signal is None:
            raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found")

        if signal.acknowledged_at is None:
            signal.acknowledged_at = datetime.now(UTC)
            signal.acknowledged_by = getattr(user, "id", None)
            db.commit()

        return {"status": "ok", "signal": _serialize(signal)}
    finally:
        db.close()


@router.post("/{signal_id}/resolve")
async def resolve_signal(signal_id: str, request: Request, user=Depends(get_current_user)):
    db = _get_db()
    try:
        signal = db.query(Signal).filter(Signal.id == signal_id).first()
        if signal is None:
            raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found")

        if signal.resolved_at is None:
            now = datetime.now(UTC)
            signal.resolved_at = now
            if signal.acknowledged_at is None:
                # Resolving implicitly acknowledges.
                signal.acknowledged_at = now
                signal.acknowledged_by = getattr(user, "id", None)
            db.commit()

        return {"status": "ok", "signal": _serialize(signal)}
    finally:
        db.close()
