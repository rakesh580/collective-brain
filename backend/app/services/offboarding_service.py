"""OffboardingService — knowledge-gap analysis when a member leaves.

Given a member_id the service computes:
  1. Unique expertise  — topics only this member contributes to
  2. Sole-contributor artifacts — artifacts where only this member has contributions
  3. Transfer recommendations — for each at-risk topic, who else can absorb it?
  4. Risk level — "low" | "medium" | "high" | "critical"
  5. Human-readable summary

Results are persisted to the offboarding_reports table so they can be retrieved later.
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.contribution import ContributionRecord
from app.models.member import MemberRecord
from app.models.offboarding_report import OffboardingReport

logger = logging.getLogger("collective_brain.offboarding")


class OffboardingResult:
    """In-memory result object returned by generate_report() before DB commit."""

    def __init__(
        self,
        member_id: str,
        unique_expertise: list[str],
        sole_contributor_artifact_ids: list[str],
        transfer_recommendations: list[dict],
        risk_level: str,
        summary: str,
        report_data: dict,
    ) -> None:
        self.member_id = member_id
        self.unique_expertise = unique_expertise
        self.sole_contributor_artifact_ids = sole_contributor_artifact_ids
        self.transfer_recommendations = transfer_recommendations
        self.risk_level = risk_level
        self.summary = summary
        self.report_data = report_data


class OffboardingService:
    """Compute and persist offboarding risk reports."""

    def generate_report(
        self,
        db: Session,
        member_id: str,
        created_by: str | None = None,
        llm_service: Any = None,
    ) -> OffboardingReport:
        """Analyse knowledge gaps caused by this member leaving and save the report."""
        member = db.query(MemberRecord).filter(MemberRecord.id == member_id).first()
        if member is None:
            raise ValueError(f"Member {member_id} not found")

        result = self._analyse(db, member, llm_service)

        # Persist
        report = OffboardingReport(
            id=str(uuid.uuid4()),
            member_id=member_id,
            created_by=created_by,
            created_at=datetime.now(UTC),
            unique_expertise=result.unique_expertise,
            sole_contributor_artifact_ids=result.sole_contributor_artifact_ids,
            transfer_recommendations=result.transfer_recommendations,
            risk_level=result.risk_level,
            summary=result.summary,
            report_data=result.report_data,
        )
        db.add(report)

        # Mark member as offboarding
        member.status = "offboarding"
        db.commit()
        db.refresh(report)
        logger.info(
            "Offboarding report %s generated for member %s (risk=%s)",
            report.id,
            member_id,
            result.risk_level,
        )
        return report

    # ── Internal analysis ──────────────────────────────────────────────────────

    def _analyse(
        self, db: Session, member: MemberRecord, llm_service: Any
    ) -> OffboardingResult:
        member_id = member.id

        # All contributions by this member
        own_contribs = (
            db.query(ContributionRecord)
            .filter(ContributionRecord.member_id == member_id)
            .all()
        )

        # Topics this member has contributed to
        own_topics: set[str] = set()
        for c in own_contribs:
            for t in (c.topics or []):
                own_topics.add(t)

        # All active members except the one leaving
        other_members = (
            db.query(MemberRecord)
            .filter(MemberRecord.id != member_id, MemberRecord.status != "offboarded")
            .all()
        )

        # Map: topic -> set of other member IDs who also cover it
        topic_coverage: dict[str, set[str]] = defaultdict(set)
        for om in other_members:
            for tag in (om.expertise_tags or []):
                topic_coverage[tag.lower()].add(om.id)

        # Unique expertise = topics this member has that NO other active member covers
        unique_expertise = [
            t for t in own_topics if t not in topic_coverage or not topic_coverage[t]
        ]

        # Sole-contributor artifacts
        own_artifact_ids = {c.artifact_id for c in own_contribs if c.artifact_id}
        sole_artifact_ids: list[str] = []
        for art_id in own_artifact_ids:
            contributor_ids = {
                c.member_id
                for c in db.query(ContributionRecord)
                .filter(ContributionRecord.artifact_id == art_id)
                .all()
            }
            if contributor_ids == {member_id}:
                sole_artifact_ids.append(art_id)

        # Transfer recommendations — for each at-risk topic find best alternative
        recommendations: list[dict] = []
        for topic in unique_expertise:
            # Find members who have overlapping expertise (expertise_tags contains any
            # related term) — first try exact match across all topics in coverage map,
            # then fall back to any member with high expertise_scores
            candidates = _find_candidates(topic, other_members)
            for cand in candidates[:3]:
                recommendations.append(
                    {
                        "topic": topic,
                        "recommended_member_id": cand.id,
                        "recommended_member_name": cand.name,
                    }
                )

        # Risk scoring
        risk_level = _compute_risk(
            unique_expertise=unique_expertise,
            sole_artifact_count=len(sole_artifact_ids),
            total_contributions=len(own_contribs),
        )

        summary = _build_summary(member, unique_expertise, sole_artifact_ids, risk_level)

        report_data = {
            "member_name": member.name,
            "own_topics": list(own_topics),
            "total_contributions": len(own_contribs),
            "unique_expertise": unique_expertise,
            "sole_contributor_artifact_ids": sole_artifact_ids,
        }

        return OffboardingResult(
            member_id=member_id,
            unique_expertise=unique_expertise,
            sole_contributor_artifact_ids=sole_artifact_ids,
            transfer_recommendations=recommendations,
            risk_level=risk_level,
            summary=summary,
            report_data=report_data,
        )

    def get_report(self, db: Session, member_id: str) -> OffboardingReport | None:
        """Return the latest report for this member, or None."""
        return (
            db.query(OffboardingReport)
            .filter(OffboardingReport.member_id == member_id)
            .order_by(OffboardingReport.created_at.desc())
            .first()
        )

    def complete_offboarding(self, db: Session, member_id: str) -> MemberRecord:
        """Mark member as fully offboarded."""
        member = db.query(MemberRecord).filter(MemberRecord.id == member_id).first()
        if member is None:
            raise ValueError(f"Member {member_id} not found")
        member.status = "offboarded"
        db.commit()
        db.refresh(member)
        return member


# ── Module-level helpers ───────────────────────────────────────────────────────

def _find_candidates(topic: str, others: list[MemberRecord]) -> list[MemberRecord]:
    """Return members ordered by how well they cover the given topic."""
    scored: list[tuple[float, MemberRecord]] = []
    for m in others:
        tags = [t.lower() for t in (m.expertise_tags or [])]
        score = float(topic in tags)
        # Boost by expertise_scores if present
        scores_map = m.expertise_scores or {}
        score += float(scores_map.get(topic, 0))
        if score > 0:
            scored.append((score, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored]


def _compute_risk(
    unique_expertise: list[str],
    sole_artifact_count: int,
    total_contributions: int,
) -> str:
    score = len(unique_expertise) * 2 + sole_artifact_count
    if score == 0:
        return "low"
    if score <= 3:
        return "medium"
    if score <= 8:
        return "high"
    return "critical"


def _build_summary(
    member: MemberRecord,
    unique_expertise: list[str],
    sole_artifact_ids: list[str],
    risk_level: str,
) -> str:
    lines = [f"Offboarding risk report for {member.name} — Risk: {risk_level.upper()}"]
    if not unique_expertise:
        lines.append("No unique expertise identified; knowledge is well distributed.")
    else:
        lines.append(
            f"Unique expertise (no other team member covers): {', '.join(unique_expertise)}."
        )
    if sole_artifact_ids:
        lines.append(
            f"{len(sole_artifact_ids)} artifact(s) have only this member as contributor "
            "and should be reviewed or reassigned."
        )
    return " ".join(lines)
