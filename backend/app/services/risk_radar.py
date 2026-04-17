"""Silent Risk Radar — detects organizational risks from work patterns."""

import logging
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.artifact import ArtifactRecord
from app.models.contribution import ContributionRecord
from app.models.decision import RiskAlert
from app.models.member import MemberRecord

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class RiskRadarService:
    """Detects organizational risks from work patterns."""

    def __init__(self):
        self.logger = logging.getLogger("collective_brain.risk_radar")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan_all_risks(self, db: Session) -> list[dict]:
        """Run all risk detection algorithms, persist alerts, return them."""
        alerts: list[dict] = []
        alerts.extend(self._detect_project_stalls(db))
        alerts.extend(self._detect_knowledge_silos(db))
        alerts.extend(self._detect_key_person_risks(db))
        alerts.extend(self._detect_collaboration_drops(db))
        alerts.extend(self._detect_expertise_concentration(db))

        # Persist new alerts
        for alert_data in alerts:
            existing = (
                db.query(RiskAlert)
                .filter(
                    RiskAlert.alert_type == alert_data["alert_type"],
                    RiskAlert.affected_entity_type == alert_data["affected_entity_type"],
                    RiskAlert.affected_entity_id == alert_data["affected_entity_id"],
                    RiskAlert.is_resolved == False,  # noqa: E712
                )
                .first()
            )
            if existing:
                # Update severity / metrics on the existing unresolved alert
                existing.severity = alert_data["severity"]
                existing.title = alert_data["title"]
                existing.description = alert_data["description"]
                existing.metrics = alert_data["metrics"]
                existing.detected_at = datetime.now(UTC)
                alert_data["id"] = existing.id
            else:
                alert_id = str(uuid.uuid4())
                alert_data["id"] = alert_id
                record = RiskAlert(
                    id=alert_id,
                    alert_type=alert_data["alert_type"],
                    severity=alert_data["severity"],
                    title=alert_data["title"],
                    description=alert_data["description"],
                    affected_entity_type=alert_data["affected_entity_type"],
                    affected_entity_id=alert_data["affected_entity_id"],
                    metrics=alert_data["metrics"],
                    detected_at=datetime.now(UTC),
                )
                db.add(record)

        try:
            db.commit()
        except Exception:
            db.rollback()
            self.logger.exception("Failed to persist risk alerts")

        alerts.sort(key=lambda a: SEVERITY_ORDER.get(a.get("severity", "low"), 99))
        self.logger.info("Risk scan completed — %d alerts detected", len(alerts))
        return alerts

    def get_active_alerts(
        self,
        db: Session,
        severity: str | None = None,
        alert_type: str | None = None,
        acknowledged: bool | None = None,
    ) -> list[dict]:
        """Get all unresolved risk alerts, sorted by severity."""
        query = db.query(RiskAlert).filter(RiskAlert.is_resolved == False)  # noqa: E712
        if severity:
            query = query.filter(RiskAlert.severity == severity)
        if alert_type:
            query = query.filter(RiskAlert.alert_type == alert_type)
        if acknowledged is not None:
            query = query.filter(RiskAlert.is_acknowledged == acknowledged)

        rows = query.order_by(RiskAlert.detected_at.desc()).all()
        alerts = [self._alert_to_dict(r) for r in rows]
        alerts.sort(key=lambda a: SEVERITY_ORDER.get(a.get("severity", "low"), 99))
        return alerts

    def get_alert_by_id(self, db: Session, alert_id: str) -> dict | None:
        """Return a single alert or None."""
        row = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
        if not row:
            return None
        return self._alert_to_dict(row)

    def acknowledge_alert(self, db: Session, alert_id: str) -> dict | None:
        """Mark an alert as acknowledged."""
        row = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
        if not row:
            return None
        row.is_acknowledged = True
        row.acknowledged_at = datetime.now(UTC)
        db.commit()
        return self._alert_to_dict(row)

    def resolve_alert(self, db: Session, alert_id: str) -> dict | None:
        """Mark an alert as resolved."""
        row = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
        if not row:
            return None
        row.is_resolved = True
        row.resolved_at = datetime.now(UTC)
        db.commit()
        return self._alert_to_dict(row)

    def get_risk_summary(self, db: Session) -> dict:
        """Return summary: total alerts by severity, by type, trend vs last scan."""
        active = db.query(RiskAlert).filter(RiskAlert.is_resolved == False).all()  # noqa: E712

        by_severity: dict[str, int] = Counter()
        by_type: dict[str, int] = Counter()
        for a in active:
            by_severity[a.severity] += 1
            by_type[a.alert_type] += 1

        # Trend: compare count of alerts detected in last 7 days vs previous 7 days
        now = datetime.now(UTC)
        recent_cutoff = now - timedelta(days=7)
        older_cutoff = now - timedelta(days=14)

        recent_count = db.query(func.count(RiskAlert.id)).filter(RiskAlert.detected_at >= recent_cutoff).scalar() or 0
        older_count = (
            db.query(func.count(RiskAlert.id))
            .filter(RiskAlert.detected_at >= older_cutoff, RiskAlert.detected_at < recent_cutoff)
            .scalar()
            or 0
        )

        if older_count == 0:
            trend = "stable" if recent_count == 0 else "increasing"
        elif recent_count > older_count:
            trend = "increasing"
        elif recent_count < older_count:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "total_alerts": len(active),
            "total_active": len(active),
            "by_severity": dict(by_severity),
            "by_type": dict(by_type),
            "critical_count": by_severity.get("critical", 0),
            "high_count": by_severity.get("high", 0),
            "medium_count": by_severity.get("medium", 0),
            "low_count": by_severity.get("low", 0),
            "trend": trend,
            "recent_count": recent_count,
            "previous_count": older_count,
        }

    # ------------------------------------------------------------------
    # Detection algorithms
    # ------------------------------------------------------------------

    def _detect_project_stalls(self, db: Session) -> list[dict]:
        """Detect projects where contribution frequency dropped > 50% week-over-week."""
        alerts: list[dict] = []
        now = datetime.now(UTC)
        recent_start = now - timedelta(days=7)
        previous_start = now - timedelta(days=14)

        # Contributions in the last 7 days grouped by artifact
        recent_rows = (
            db.query(
                ContributionRecord.artifact_id,
                func.count(ContributionRecord.id).label("cnt"),
            )
            .filter(
                ContributionRecord.timestamp >= recent_start,
                ContributionRecord.artifact_id.isnot(None),
            )
            .group_by(ContributionRecord.artifact_id)
            .all()
        )
        recent_map: dict[str, int] = {r.artifact_id: r.cnt for r in recent_rows}

        # Contributions in the previous 7 days grouped by artifact
        previous_rows = (
            db.query(
                ContributionRecord.artifact_id,
                func.count(ContributionRecord.id).label("cnt"),
            )
            .filter(
                ContributionRecord.timestamp >= previous_start,
                ContributionRecord.timestamp < recent_start,
                ContributionRecord.artifact_id.isnot(None),
            )
            .group_by(ContributionRecord.artifact_id)
            .all()
        )
        previous_map: dict[str, int] = {r.artifact_id: r.cnt for r in previous_rows}

        # Check each artifact that had activity in the previous period
        for artifact_id, prev_count in previous_map.items():
            if prev_count < 2:
                continue  # Ignore very low-activity artifacts
            curr_count = recent_map.get(artifact_id, 0)
            drop_pct = ((prev_count - curr_count) / prev_count) * 100

            if drop_pct >= 50:
                artifact = db.query(ArtifactRecord).filter(ArtifactRecord.id == artifact_id).first()
                title = artifact.title if artifact else artifact_id
                severity = "critical" if drop_pct >= 90 else ("high" if drop_pct >= 75 else "medium")
                alerts.append(
                    {
                        "alert_type": "project_stall",
                        "severity": severity,
                        "title": f"Activity drop on '{title}'",
                        "description": (
                            f"Contributions to '{title}' dropped {drop_pct:.0f}% "
                            f"(from {prev_count} to {curr_count} in the last 7 days)."
                        ),
                        "affected_entity_type": "artifact",
                        "affected_entity_id": artifact_id,
                        "metrics": {
                            "previous_count": prev_count,
                            "current_count": curr_count,
                            "drop_percentage": round(drop_pct, 1),
                        },
                    }
                )

        return alerts

    def _detect_knowledge_silos(self, db: Session) -> list[dict]:
        """Find expertise areas covered by fewer than 2 active members."""
        alerts: list[dict] = []
        members = db.query(MemberRecord).filter(MemberRecord.status == "active").all()
        if not members:
            return alerts

        tag_members: dict[str, list[str]] = defaultdict(list)
        for m in members:
            tags = m.expertise_tags if isinstance(m.expertise_tags, list) else []
            for tag in tags:
                tag_members[tag].append(m.name)

        for tag, names in tag_members.items():
            if len(names) < 2:
                severity = "critical" if len(names) == 0 else "high"
                alerts.append(
                    {
                        "alert_type": "knowledge_silo",
                        "severity": severity,
                        "title": f"Knowledge silo: '{tag}'",
                        "description": (
                            f"The expertise area '{tag}' is covered by only {len(names)} "
                            f"active member(s): {', '.join(names) or 'none'}. "
                            "If they become unavailable, this knowledge area has no backup."
                        ),
                        "affected_entity_type": "expertise_tag",
                        "affected_entity_id": tag,
                        "metrics": {
                            "member_count": len(names),
                            "members": names,
                        },
                    }
                )

        return alerts

    def _detect_key_person_risks(self, db: Session) -> list[dict]:
        """Find members who are single points of failure."""
        alerts: list[dict] = []
        members = db.query(MemberRecord).filter(MemberRecord.status == "active").all()
        if not members:
            return alerts

        # Build tag-to-member mapping for uniqueness check
        tag_members: dict[str, list[str]] = defaultdict(list)
        for m in members:
            tags = m.expertise_tags if isinstance(m.expertise_tags, list) else []
            for tag in tags:
                tag_members[tag].append(m.id)

        for member in members:
            risk_factors: list[str] = []

            # Check sole-contributor artifacts
            contributions = (
                db.query(ContributionRecord.artifact_id)
                .filter(
                    ContributionRecord.member_id == member.id,
                    ContributionRecord.artifact_id.isnot(None),
                )
                .distinct()
                .all()
            )
            sole_artifact_count = 0
            for (artifact_id,) in contributions:
                other_count = (
                    db.query(func.count(func.distinct(ContributionRecord.member_id)))
                    .filter(
                        ContributionRecord.artifact_id == artifact_id,
                        ContributionRecord.member_id != member.id,
                    )
                    .scalar()
                    or 0
                )
                if other_count == 0:
                    sole_artifact_count += 1

            if sole_artifact_count >= 3:
                risk_factors.append(f"sole contributor to {sole_artifact_count} artifacts")

            # Check unique expertise tags
            member_tags = member.expertise_tags if isinstance(member.expertise_tags, list) else []
            unique_tags = [t for t in member_tags if len(tag_members.get(t, [])) <= 1]
            if unique_tags:
                risk_factors.append(f"unique expertise in: {', '.join(unique_tags)}")

            if not risk_factors:
                continue

            severity = "critical" if (sole_artifact_count >= 5 or len(unique_tags) >= 3) else "high"
            alerts.append(
                {
                    "alert_type": "key_person_risk",
                    "severity": severity,
                    "title": f"Key-person risk: {member.name}",
                    "description": (
                        f"{member.name} is a single point of failure — "
                        + "; ".join(risk_factors)
                        + ". Consider cross-training or documentation."
                    ),
                    "affected_entity_type": "member",
                    "affected_entity_id": member.id,
                    "metrics": {
                        "sole_artifact_count": sole_artifact_count,
                        "unique_expertise_tags": unique_tags,
                        "risk_factors": risk_factors,
                    },
                }
            )

        return alerts

    def _detect_collaboration_drops(self, db: Session) -> list[dict]:
        """Detect when recent artifacts are predominantly single-contributor."""
        alerts: list[dict] = []
        now = datetime.now(UTC)
        recent_cutoff = now - timedelta(days=14)
        older_cutoff = now - timedelta(days=28)

        def _multi_contributor_ratio(start: datetime, end: datetime) -> tuple[float, int]:
            artifacts = (
                db.query(ArtifactRecord)
                .filter(
                    ArtifactRecord.ingested_at >= start,
                    ArtifactRecord.ingested_at < end,
                )
                .all()
            )
            if not artifacts:
                return 0.0, 0
            multi = 0
            for a in artifacts:
                member_ids = a.member_ids if isinstance(a.member_ids, list) else []
                if len(member_ids) > 1:
                    multi += 1
            return (multi / len(artifacts)) * 100, len(artifacts)

        recent_ratio, recent_total = _multi_contributor_ratio(recent_cutoff, now)
        older_ratio, older_total = _multi_contributor_ratio(older_cutoff, recent_cutoff)

        if older_total >= 3 and recent_total >= 3 and older_ratio > 0:
            drop = older_ratio - recent_ratio
            if drop >= 20:
                severity = "high" if drop >= 40 else "medium"
                alerts.append(
                    {
                        "alert_type": "collaboration_drop",
                        "severity": severity,
                        "title": "Cross-team collaboration declining",
                        "description": (
                            f"Multi-contributor artifacts dropped from {older_ratio:.0f}% to "
                            f"{recent_ratio:.0f}% over the last two weeks. "
                            "This may indicate siloed work patterns."
                        ),
                        "affected_entity_type": "team",
                        "affected_entity_id": "all",
                        "metrics": {
                            "recent_multi_pct": round(recent_ratio, 1),
                            "previous_multi_pct": round(older_ratio, 1),
                            "drop_percentage": round(drop, 1),
                            "recent_artifact_count": recent_total,
                            "previous_artifact_count": older_total,
                        },
                    }
                )

        return alerts

    def _detect_expertise_concentration(self, db: Session) -> list[dict]:
        """Flag expertise areas where active-expert ratio is below threshold."""
        alerts: list[dict] = []
        members = db.query(MemberRecord).filter(MemberRecord.status == "active").all()
        if len(members) < 3:
            return alerts  # Too few members to assess concentration

        total_members = len(members)
        tag_members: dict[str, list[str]] = defaultdict(list)
        for m in members:
            tags = m.expertise_tags if isinstance(m.expertise_tags, list) else []
            for tag in tags:
                tag_members[tag].append(m.name)

        threshold = 0.15  # If fewer than 15% of team knows a topic, flag it
        for tag, names in tag_members.items():
            ratio = len(names) / total_members
            if ratio < threshold and len(names) <= 2:
                severity = "medium" if len(names) == 2 else "high"
                alerts.append(
                    {
                        "alert_type": "expertise_concentration",
                        "severity": severity,
                        "title": f"Expertise concentration: '{tag}'",
                        "description": (
                            f"Only {len(names)}/{total_members} active members "
                            f"({ratio:.0%}) have expertise in '{tag}': {', '.join(names)}. "
                            "Consider cross-training to reduce risk."
                        ),
                        "affected_entity_type": "expertise_tag",
                        "affected_entity_id": tag,
                        "metrics": {
                            "expert_count": len(names),
                            "total_members": total_members,
                            "ratio": round(ratio, 3),
                            "experts": names,
                        },
                    }
                )

        return alerts

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _alert_to_dict(row: RiskAlert) -> dict:
        return {
            "id": row.id,
            "alert_type": row.alert_type,
            "severity": row.severity,
            "title": row.title,
            "description": row.description,
            "affected_entity_type": row.affected_entity_type,
            "affected_entity_id": row.affected_entity_id,
            "metrics": row.metrics if isinstance(row.metrics, dict) else {},
            "is_acknowledged": bool(row.is_acknowledged),
            "is_resolved": bool(row.is_resolved),
            "detected_at": row.detected_at.isoformat() if row.detected_at else None,
            "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        }
