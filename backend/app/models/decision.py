from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String

from app.db.database import Base


class DecisionRecord(Base):
    __tablename__ = "decisions"

    id = Column(String, primary_key=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    decision_type = Column(String, default="technical")
    status = Column(String, default="active")
    confidence_score = Column(Float, default=0.0)
    context_summary = Column(String, nullable=True)
    alternatives_considered = Column(JSON, default=list)
    outcome_summary = Column(String, nullable=True)
    source_artifact_ids = Column(JSON, default=list)
    source_chunk_ids = Column(JSON, default=list)
    involved_member_ids = Column(JSON, default=list)
    tags = Column(JSON, default=list)
    decided_at = Column(DateTime, nullable=True)
    extracted_at = Column(DateTime, default=lambda: datetime.now(UTC))
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class DecisionLink(Base):
    __tablename__ = "decision_links"

    id = Column(String, primary_key=True)
    from_decision_id = Column(String, ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False, index=True)
    to_decision_id = Column(String, ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False, index=True)
    link_type = Column(String, default="related")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class RiskAlert(Base):
    __tablename__ = "risk_alerts"

    id = Column(String, primary_key=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    alert_type = Column(String, nullable=False)
    severity = Column(String, default="medium")
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    affected_entity_type = Column(String, nullable=True)
    affected_entity_id = Column(String, nullable=True)
    metrics = Column(JSON, default=dict)
    is_acknowledged = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    detected_at = Column(DateTime, default=lambda: datetime.now(UTC))
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)


class ContinuityScore(Base):
    __tablename__ = "continuity_scores"

    id = Column(String, primary_key=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False, index=True)
    entity_name = Column(String, nullable=False)
    score = Column(Float, default=0.0)
    risk_level = Column(String, default="medium")
    factors = Column(JSON, default=dict)
    recommendations = Column(JSON, default=list)
    calculated_at = Column(DateTime, default=lambda: datetime.now(UTC))


class DecisionOutcome(Base):
    __tablename__ = "decision_outcomes"
    id = Column(String, primary_key=True)
    decision_id = Column(String, ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False, index=True)
    outcome_description = Column(String, nullable=False)
    outcome_status = Column(String, default="unknown")  # positive, negative, mixed, unknown
    lessons_learned = Column(JSON, default=list)
    recorded_by = Column(String, nullable=True)  # user_id
    recorded_at = Column(DateTime, default=lambda: datetime.now(UTC))


class NotificationWebhook(Base):
    __tablename__ = "notification_webhooks"
    id = Column(String, primary_key=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    url = Column(String, nullable=False)
    event_types = Column(JSON, default=list)  # ["risk_alert", "decision_extracted", ...]
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    last_triggered_at = Column(DateTime, nullable=True)


class NotificationLog(Base):
    __tablename__ = "notification_logs"
    id = Column(String, primary_key=True)
    webhook_id = Column(String, ForeignKey("notification_webhooks.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    payload_summary = Column(String, nullable=True)
    success = Column(Boolean, default=False)
    response_code = Column(Integer, nullable=True)
    error_message = Column(String, nullable=True)
    sent_at = Column(DateTime, default=lambda: datetime.now(UTC))
