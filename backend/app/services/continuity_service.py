"""Knowledge Continuity Score — measures how resilient the org is if someone leaves."""

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.artifact import ArtifactRecord
from app.models.contribution import ContributionRecord
from app.models.decision import ContinuityScore
from app.models.member import MemberRecord


class ContinuityScoreService:
    """Calculates knowledge continuity scores — how resilient is the org if someone leaves?"""

    def __init__(self):
        self.logger = logging.getLogger("collective_brain.continuity")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_member_continuity(self, db: Session, member_id: str) -> dict:
        """Calculate what happens if this member leaves.

        Returns a dict with score (0-100, higher = more resilient), risk details,
        and actionable recommendations.
        """
        member = db.query(MemberRecord).filter(MemberRecord.id == member_id).first()
        if not member:
            return {
                "member_id": member_id,
                "member_name": "Unknown",
                "score": 100,
                "risk_level": "low",
                "knowledge_areas_at_risk": [],
                "artifacts_at_risk": 0,
                "backup_members": {},
                "recommendations": [],
            }

        impact_score, factors = self._score_member_impact(db, member)
        # Continuity score is the inverse of impact — high impact = low continuity
        continuity_score = max(0.0, min(100.0, 100.0 - impact_score))
        risk_level = self._risk_level(continuity_score)

        return {
            "member_id": member.id,
            "member_name": member.name,
            "score": round(continuity_score, 1),
            "risk_level": risk_level,
            "knowledge_areas_at_risk": factors.get("unique_tags", []),
            "artifacts_at_risk": factors.get("sole_artifact_count", 0),
            "backup_members": factors.get("backup_members", {}),
            "recommendations": self._member_recommendations(member, factors),
        }

    def calculate_team_continuity(self, db: Session) -> dict:
        """Calculate overall team knowledge continuity."""
        members = db.query(MemberRecord).filter(MemberRecord.status == "active").all()
        if not members:
            return {
                "overall_score": 0,
                "risk_level": "critical",
                "member_scores": [],
                "weakest_links": [],
                "knowledge_gaps": [],
                "recommendations": ["No active members found. Ingest team data to begin analysis."],
            }

        member_results = []
        for m in members:
            result = self.calculate_member_continuity(db, m.id)
            member_results.append(result)

        # Overall score = weighted average, weighted more by lower (riskier) scores
        if member_results:
            scores = [r["score"] for r in member_results]
            # Use harmonic-ish mean to penalize low scores more
            weights = [max(1.0, 101.0 - s) for s in scores]
            overall = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
        else:
            overall = 0

        # Weakest links: members whose departure would hurt the most
        weakest = sorted(member_results, key=lambda r: r["score"])[:5]

        # Knowledge gaps: tags with no backup
        all_gaps: list[str] = []
        for r in member_results:
            all_gaps.extend(r.get("knowledge_areas_at_risk", []))
        unique_gaps = sorted(set(all_gaps))

        return {
            "overall_score": round(overall, 1),
            "risk_level": self._risk_level(overall),
            "member_count": len(members),
            "member_scores": sorted(member_results, key=lambda r: r["score"]),
            "weakest_links": weakest,
            "knowledge_gaps": unique_gaps,
            "recommendations": self._team_recommendations(member_results, unique_gaps),
        }

    def calculate_project_continuity(self, db: Session, artifact_ids: list[str]) -> dict:
        """Calculate continuity for a specific project (set of artifacts)."""
        if not artifact_ids:
            return {
                "score": 0,
                "risk_level": "critical",
                "artifact_count": 0,
                "contributor_count": 0,
                "contributors": [],
                "single_contributor_artifacts": [],
                "recommendations": ["No artifacts specified."],
            }

        artifacts = (
            db.query(ArtifactRecord)
            .filter(ArtifactRecord.id.in_(artifact_ids))
            .all()
        )
        if not artifacts:
            return {
                "score": 0,
                "risk_level": "critical",
                "artifact_count": 0,
                "contributor_count": 0,
                "contributors": [],
                "single_contributor_artifacts": [],
                "recommendations": ["None of the specified artifacts were found."],
            }

        # Gather all contributors
        all_contributor_ids: set[str] = set()
        single_contributor_artifacts: list[dict] = []

        for a in artifacts:
            member_ids = a.member_ids if isinstance(a.member_ids, list) else []
            all_contributor_ids.update(member_ids)
            if len(member_ids) <= 1:
                single_contributor_artifacts.append({
                    "artifact_id": a.id,
                    "title": a.title or a.id,
                    "contributor_count": len(member_ids),
                })

        # Check if contributors are still active
        active_contributors = (
            db.query(MemberRecord)
            .filter(
                MemberRecord.id.in_(list(all_contributor_ids)),
                MemberRecord.status == "active",
            )
            .all()
            if all_contributor_ids
            else []
        )
        active_ids = {m.id for m in active_contributors}
        inactive_count = len(all_contributor_ids - active_ids)

        # Score factors
        total = len(artifacts)
        single_ratio = len(single_contributor_artifacts) / total if total > 0 else 1.0
        contributor_count = len(all_contributor_ids)
        active_ratio = len(active_ids) / contributor_count if contributor_count > 0 else 0.0

        # Score: penalize single-contributor artifacts and inactive contributors
        score = 100.0
        score -= single_ratio * 50  # Up to -50 for single-contributor artifacts
        score -= (1.0 - active_ratio) * 30  # Up to -30 for inactive contributors
        if contributor_count <= 1:
            score -= 20  # Only one person knows the whole project
        score = max(0.0, min(100.0, score))

        recommendations: list[str] = []
        if single_contributor_artifacts:
            recommendations.append(
                f"{len(single_contributor_artifacts)}/{total} artifacts have a single contributor. "
                "Encourage pair reviews or knowledge-sharing sessions."
            )
        if inactive_count > 0:
            recommendations.append(
                f"{inactive_count} contributor(s) are no longer active. "
                "Ensure their knowledge is documented and handed off."
            )
        if contributor_count <= 1:
            recommendations.append(
                "This project has only one contributor. Assign a backup contributor."
            )
        if not recommendations:
            recommendations.append("Project continuity looks healthy. Keep up the collaborative work.")

        return {
            "score": round(score, 1),
            "risk_level": self._risk_level(score),
            "artifact_count": total,
            "contributor_count": contributor_count,
            "active_contributor_count": len(active_ids),
            "inactive_contributor_count": inactive_count,
            "contributors": [
                {"id": m.id, "name": m.name, "status": m.status}
                for m in active_contributors
            ],
            "single_contributor_artifacts": single_contributor_artifacts,
            "recommendations": recommendations,
        }

    def get_continuity_dashboard(self, db: Session) -> dict:
        """Return full continuity dashboard data."""
        team_data = self.calculate_team_continuity(db)

        # Load the most recent saved scores for trend comparison
        latest_scores = (
            db.query(ContinuityScore)
            .filter(ContinuityScore.entity_type == "team")
            .order_by(ContinuityScore.calculated_at.desc())
            .limit(2)
            .all()
        )

        trend = "stable"
        if len(latest_scores) >= 2:
            current = latest_scores[0].score
            previous = latest_scores[1].score
            if current > previous + 2:
                trend = "improving"
            elif current < previous - 2:
                trend = "declining"

        # Build structured knowledge gaps with member info
        all_members = db.query(MemberRecord).filter(MemberRecord.status == "active").all()

        structured_gaps = []
        backed_up_count = 0
        all_tags: set[str] = set()
        for m in all_members:
            tags = m.expertise_tags or []
            for t in tags:
                all_tags.add(t)

        for tag in all_tags:
            members_with_tag = [m.name for m in all_members if tag in (m.expertise_tags or [])]
            if len(members_with_tag) < 2:
                structured_gaps.append({
                    "tag": tag,
                    "member_count": len(members_with_tag),
                    "members": members_with_tag,
                })
            else:
                backed_up_count += 1

        return {
            "overall_score": team_data["overall_score"],
            "risk_level": team_data["risk_level"],
            "members_at_risk": team_data.get("weakest_links", []),
            "knowledge_gaps": structured_gaps,
            "recommendations": team_data.get("recommendations", []),
            "trend": trend,
            "total_members": team_data.get("member_count", 0),
            "member_count": team_data.get("member_count", 0),
            "backed_up_areas": backed_up_count,
        }

    def save_continuity_snapshot(self, db: Session) -> dict:
        """Recalculate and persist continuity scores for the whole team."""
        team_data = self.calculate_team_continuity(db)

        # Save team-level score
        team_score_id = str(uuid.uuid4())
        team_record = ContinuityScore(
            id=team_score_id,
            entity_type="team",
            entity_id="all",
            entity_name="Team Overall",
            score=team_data["overall_score"],
            risk_level=team_data["risk_level"],
            factors={
                "member_count": team_data.get("member_count", 0),
                "knowledge_gaps": team_data.get("knowledge_gaps", []),
            },
            recommendations=team_data.get("recommendations", []),
            calculated_at=datetime.now(UTC),
        )
        db.add(team_record)

        # Save per-member scores
        member_scores = team_data.get("member_scores", [])
        for ms in member_scores:
            score_id = str(uuid.uuid4())
            record = ContinuityScore(
                id=score_id,
                entity_type="member",
                entity_id=ms["member_id"],
                entity_name=ms["member_name"],
                score=ms["score"],
                risk_level=ms["risk_level"],
                factors={
                    "knowledge_areas_at_risk": ms.get("knowledge_areas_at_risk", []),
                    "artifacts_at_risk": ms.get("artifacts_at_risk", 0),
                },
                recommendations=ms.get("recommendations", []),
                calculated_at=datetime.now(UTC),
            )
            db.add(record)

        try:
            db.commit()
            self.logger.info(
                "Continuity snapshot saved — team score %.1f, %d members",
                team_data["overall_score"],
                len(member_scores),
            )
        except Exception:
            db.rollback()
            self.logger.exception("Failed to save continuity snapshot")

        return {
            "team_score_id": team_score_id,
            "overall_score": team_data["overall_score"],
            "risk_level": team_data["risk_level"],
            "members_calculated": len(member_scores),
            "calculated_at": datetime.now(UTC).isoformat(),
        }

    # ------------------------------------------------------------------
    # Internal scoring
    # ------------------------------------------------------------------

    def _score_member_impact(self, db: Session, member: MemberRecord) -> tuple[float, dict]:
        """Calculate 0-100 impact score for a member's departure.

        Higher score = more impact = lower continuity if they leave.
        """
        all_active_members = (
            db.query(MemberRecord)
            .filter(MemberRecord.status == "active")
            .all()
        )
        total_active = len(all_active_members)

        # --- Factor 1: Unique expertise tags (heavy weight, up to 35 pts) ---
        tag_members: dict[str, list[str]] = defaultdict(list)
        for m in all_active_members:
            tags = m.expertise_tags if isinstance(m.expertise_tags, list) else []
            for tag in tags:
                tag_members[tag].append(m.id)

        member_tags = member.expertise_tags if isinstance(member.expertise_tags, list) else []
        unique_tags = [t for t in member_tags if len(tag_members.get(t, [])) <= 1]
        unique_tag_score = min(35.0, len(unique_tags) * 12.0)

        # --- Factor 2: Sole contributor artifacts (heavy weight, up to 30 pts) ---
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

        sole_artifact_score = min(30.0, sole_artifact_count * 8.0)

        # --- Factor 3: Contribution volume relative to team (moderate, up to 15 pts) ---
        total_contributions = member.total_contributions or 0
        if total_active > 1:
            avg_contributions = sum(
                (m.total_contributions or 0) for m in all_active_members
            ) / total_active
            if avg_contributions > 0:
                volume_ratio = total_contributions / avg_contributions
                volume_score = min(15.0, max(0.0, (volume_ratio - 1.0) * 10.0))
            else:
                volume_score = 0.0
        else:
            volume_score = 15.0  # Only member

        # --- Factor 4: Recency of activity (moderate, up to 10 pts) ---
        now = datetime.now(UTC)
        days_since_active = 999
        if member.last_active:
            last_active = member.last_active
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=UTC)
            delta = now - last_active
            days_since_active = delta.days

        if days_since_active <= 7:
            recency_score = 10.0  # Very recent = high impact if they leave
        elif days_since_active <= 30:
            recency_score = 7.0
        elif days_since_active <= 90:
            recency_score = 3.0
        else:
            recency_score = 0.0  # Already inactive — lower impact

        # --- Factor 5: Backup coverage (moderate, up to 10 pts) ---
        backup_members: dict[str, list[str]] = {}
        for tag in member_tags:
            others = [
                m.name for m in all_active_members
                if m.id != member.id
                and isinstance(m.expertise_tags, list)
                and tag in m.expertise_tags
            ]
            backup_members[tag] = others

        if member_tags:
            covered_tags = sum(1 for others in backup_members.values() if others)
            coverage_ratio = covered_tags / len(member_tags)
            backup_score = (1.0 - coverage_ratio) * 10.0
        else:
            backup_score = 0.0

        impact = unique_tag_score + sole_artifact_score + volume_score + recency_score + backup_score
        impact = max(0.0, min(100.0, impact))

        factors = {
            "unique_tags": unique_tags,
            "sole_artifact_count": sole_artifact_count,
            "total_contributions": total_contributions,
            "days_since_active": days_since_active,
            "backup_members": backup_members,
            "score_breakdown": {
                "unique_expertise": round(unique_tag_score, 1),
                "sole_artifacts": round(sole_artifact_score, 1),
                "contribution_volume": round(volume_score, 1),
                "recency": round(recency_score, 1),
                "backup_coverage": round(backup_score, 1),
            },
        }

        return impact, factors

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    @staticmethod
    def _member_recommendations(member: MemberRecord, factors: dict) -> list[str]:
        """Generate actionable recommendations for improving continuity around a member."""
        recs: list[str] = []
        unique_tags = factors.get("unique_tags", [])
        sole_count = factors.get("sole_artifact_count", 0)
        backup = factors.get("backup_members", {})

        if unique_tags:
            recs.append(
                f"Cross-train another team member on: {', '.join(unique_tags)}. "
                f"{member.name} is the only person with this expertise."
            )

        if sole_count > 0:
            recs.append(
                f"Add a second contributor to {sole_count} artifact(s) where {member.name} "
                "is the sole contributor. Pair programming or code reviews help."
            )

        uncovered = [tag for tag, others in backup.items() if not others]
        if uncovered and uncovered != unique_tags:
            recs.append(
                f"No backup exists for: {', '.join(uncovered)}. "
                "Schedule knowledge-sharing sessions."
            )

        partially_covered = [
            tag for tag, others in backup.items()
            if len(others) == 1
        ]
        if partially_covered:
            recs.append(
                f"Only one backup for: {', '.join(partially_covered)}. "
                "Consider training a second backup."
            )

        if not recs:
            recs.append(
                f"{member.name}'s knowledge is well-distributed. "
                "Continue current collaboration practices."
            )

        return recs

    @staticmethod
    def _team_recommendations(member_results: list[dict], knowledge_gaps: list[str]) -> list[str]:
        """Generate team-level recommendations."""
        recs: list[str] = []

        critical_members = [r for r in member_results if r["risk_level"] == "critical"]
        if critical_members:
            names = ", ".join(r["member_name"] for r in critical_members[:3])
            recs.append(
                f"Priority: address critical key-person risk for {names}. "
                "Their departure would significantly impact team knowledge."
            )

        if knowledge_gaps:
            if len(knowledge_gaps) <= 5:
                recs.append(
                    f"Knowledge gaps with no backup: {', '.join(knowledge_gaps)}. "
                    "Cross-train at least one additional member in each area."
                )
            else:
                recs.append(
                    f"{len(knowledge_gaps)} expertise areas have no backup coverage. "
                    f"Top priorities: {', '.join(knowledge_gaps[:5])}."
                )

        high_risk = [r for r in member_results if r["risk_level"] in ("critical", "high")]
        if len(high_risk) > len(member_results) * 0.5 and len(member_results) >= 3:
            recs.append(
                "Over half the team poses high continuity risk. "
                "Implement regular knowledge-sharing sessions and pair rotations."
            )

        sole_artifact_total = sum(r.get("artifacts_at_risk", 0) for r in member_results)
        if sole_artifact_total > 0:
            recs.append(
                f"{sole_artifact_total} artifact(s) have only a single contributor. "
                "Introduce mandatory peer reviews for all artifacts."
            )

        if not recs:
            recs.append(
                "Team knowledge continuity is healthy. "
                "Maintain current collaboration and review practices."
            )

        return recs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _risk_level(score: float) -> str:
        if score >= 80:
            return "low"
        if score >= 60:
            return "medium"
        if score >= 40:
            return "high"
        return "critical"
