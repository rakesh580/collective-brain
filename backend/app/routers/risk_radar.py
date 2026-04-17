"""Risk Radar router — API endpoints for silent risk detection."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.db.database import create_session
from app.dependencies import get_current_user
from app.services.risk_radar import RiskRadarService

router = APIRouter()

_service = RiskRadarService()


def _get_db():
    return create_session()


@router.post("/scan")
async def trigger_risk_scan(
    request: Request,
    user=Depends(get_current_user),
):
    """Trigger a full risk scan across all detection algorithms.

    Returns all detected alerts sorted by severity.
    """
    db = _get_db()
    try:
        alerts = _service.scan_all_risks(db)
        return {
            "status": "completed",
            "alert_count": len(alerts),
            "alerts": alerts,
        }
    finally:
        db.close()


@router.get("/alerts")
async def get_active_alerts(
    request: Request,
    severity: str | None = Query(default=None, description="Filter by severity: critical, high, medium, low"),
    alert_type: str | None = Query(default=None, description="Filter by alert type"),
    acknowledged: bool | None = Query(default=None, description="Filter by acknowledged status"),
    user=Depends(get_current_user),
):
    """Get all active (unresolved) risk alerts."""
    db = _get_db()
    try:
        alerts = _service.get_active_alerts(
            db,
            severity=severity,
            alert_type=alert_type,
            acknowledged=acknowledged,
        )
        return {
            "count": len(alerts),
            "alerts": alerts,
        }
    finally:
        db.close()


@router.get("/alerts/{alert_id}")
async def get_alert_detail(
    alert_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    """Get detail for a single risk alert."""
    db = _get_db()
    try:
        alert = _service.get_alert_by_id(db, alert_id)
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found",
            )
        return alert
    finally:
        db.close()


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    """Mark an alert as acknowledged."""
    db = _get_db()
    try:
        result = _service.acknowledge_alert(db, alert_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found",
            )
        return result
    finally:
        db.close()


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    """Mark an alert as resolved."""
    db = _get_db()
    try:
        result = _service.resolve_alert(db, alert_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found",
            )
        return result
    finally:
        db.close()


@router.get("/summary")
async def get_risk_summary(
    request: Request,
    user=Depends(get_current_user),
):
    """Get risk summary dashboard — counts by type/severity and trend."""
    db = _get_db()
    try:
        return _service.get_risk_summary(db)
    finally:
        db.close()
