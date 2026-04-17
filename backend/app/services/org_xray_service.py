"""Organizational X-Ray — deep analysis of how the org works."""

import logging
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.artifact import ArtifactRecord
from app.models.contribution import ContributionRecord
from app.models.decision import DecisionRecord
from app.models.knowledge_embedding import KnowledgeEmbedding
from app.models.member import MemberRecord

logger = logging.getLogger("collective_brain.org_xray")


class OrgXrayService:
    """Organizational X-Ray — deep analysis of how the org works."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_org_xray(self, db: Session) -> dict:
        """Generate a comprehensive organizational analysis."""
        now = datetime.now(UTC)

        # ── Summary stats ─────────────────────────────────────────────
        total_members = db.query(func.count(MemberRecord.id)).scalar() or 0
        total_artifacts = db.query(func.count(ArtifactRecord.id)).scalar() or 0
        total_decisions = db.query(func.count(DecisionRecord.id)).scalar() or 0
        total_chunks = db.query(func.count(KnowledgeEmbedding.id)).scalar() or 0

        earliest_artifact = (
            db.query(func.min(ArtifactRecord.ingested_at)).scalar()
        )
        active_since = earliest_artifact.isoformat() if earliest_artifact else now.isoformat()

        summary = {
            "total_members": total_members,
            "total_artifacts": total_artifacts,
            "total_decisions": total_decisions,
            "total_knowledge_chunks": total_chunks,
            "active_since": active_since,
        }

        # ── Knowledge map ─────────────────────────────────────────────
        knowledge_map = self._build_knowledge_map(db)

        # ── Team dynamics ─────────────────────────────────────────────
        team_dynamics = self._analyze_team_dynamics(db)

        # ── Decision patterns ─────────────────────────────────────────
        decision_patterns = self._analyze_decision_patterns(db, now)

        # ── Risk profile ──────────────────────────────────────────────
        risk_profile = self._analyze_risk_profile(db)

        # ── Recommendations ───────────────────────────────────────────
        recommendations = self._generate_recommendations(
            summary, knowledge_map, team_dynamics, decision_patterns, risk_profile
        )

        return {
            "generated_at": now.isoformat(),
            "summary": summary,
            "knowledge_map": knowledge_map,
            "team_dynamics": team_dynamics,
            "decision_patterns": decision_patterns,
            "risk_profile": risk_profile,
            "recommendations": recommendations,
        }

    def compare_teams(
        self,
        db: Session,
        team_a_member_ids: list[str],
        team_b_member_ids: list[str],
    ) -> dict:
        """Compare two teams for M&A analysis.

        Returns overlap areas, unique strengths of each team,
        potential synergies, and integration risks.
        """
        team_a_members = (
            db.query(MemberRecord)
            .filter(MemberRecord.id.in_(team_a_member_ids))
            .all()
            if team_a_member_ids else []
        )
        team_b_members = (
            db.query(MemberRecord)
            .filter(MemberRecord.id.in_(team_b_member_ids))
            .all()
            if team_b_member_ids else []
        )

        # Gather expertise tags for each team
        team_a_tags: set[str] = set()
        team_a_tag_members: dict[str, list[str]] = defaultdict(list)
        for m in team_a_members:
            tags = m.expertise_tags if isinstance(m.expertise_tags, list) else []
            for t in tags:
                team_a_tags.add(t)
                team_a_tag_members[t].append(m.name)

        team_b_tags: set[str] = set()
        team_b_tag_members: dict[str, list[str]] = defaultdict(list)
        for m in team_b_members:
            tags = m.expertise_tags if isinstance(m.expertise_tags, list) else []
            for t in tags:
                team_b_tags.add(t)
                team_b_tag_members[t].append(m.name)

        overlap_tags = team_a_tags & team_b_tags
        unique_a = team_a_tags - team_b_tags
        unique_b = team_b_tags - team_a_tags

        # Contribution stats for each team
        a_contribution_count = (
            db.query(func.count(ContributionRecord.id))
            .filter(ContributionRecord.member_id.in_(team_a_member_ids))
            .scalar() or 0
        ) if team_a_member_ids else 0

        b_contribution_count = (
            db.query(func.count(ContributionRecord.id))
            .filter(ContributionRecord.member_id.in_(team_b_member_ids))
            .scalar() or 0
        ) if team_b_member_ids else 0

        # Decisions involvement
        all_decisions = db.query(DecisionRecord).all()
        a_decision_count = 0
        b_decision_count = 0
        shared_decision_count = 0
        a_ids_set = set(team_a_member_ids)
        b_ids_set = set(team_b_member_ids)

        for dec in all_decisions:
            involved = set(dec.involved_member_ids) if isinstance(dec.involved_member_ids, list) else set()
            a_involved = bool(involved & a_ids_set)
            b_involved = bool(involved & b_ids_set)
            if a_involved and b_involved:
                shared_decision_count += 1
            if a_involved:
                a_decision_count += 1
            if b_involved:
                b_decision_count += 1

        # Synergies: areas where combining teams creates better coverage
        synergies = []
        for tag in unique_a:
            synergies.append(
                f"Team A brings unique expertise in '{tag}' ({', '.join(team_a_tag_members[tag])})"
            )
        for tag in unique_b:
            synergies.append(
                f"Team B brings unique expertise in '{tag}' ({', '.join(team_b_tag_members[tag])})"
            )

        # Integration risks
        integration_risks = []
        if overlap_tags:
            integration_risks.append(
                f"Overlapping expertise in {len(overlap_tags)} area(s) "
                f"({', '.join(sorted(overlap_tags)[:5])}) may lead to role ambiguity."
            )
        if not overlap_tags:
            integration_risks.append(
                "No overlapping expertise — teams may struggle to find common ground."
            )
        combined_members = len(team_a_member_ids) + len(team_b_member_ids)
        if combined_members > 0:
            size_ratio = max(len(team_a_member_ids), len(team_b_member_ids)) / combined_members
            if size_ratio > 0.8:
                integration_risks.append(
                    "Significant size imbalance between teams may cause cultural friction."
                )

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "team_a": {
                "member_count": len(team_a_members),
                "members": [{"id": m.id, "name": m.name} for m in team_a_members],
                "expertise_areas": sorted(team_a_tags),
                "total_contributions": a_contribution_count,
                "decisions_involved": a_decision_count,
            },
            "team_b": {
                "member_count": len(team_b_members),
                "members": [{"id": m.id, "name": m.name} for m in team_b_members],
                "expertise_areas": sorted(team_b_tags),
                "total_contributions": b_contribution_count,
                "decisions_involved": b_decision_count,
            },
            "overlap": {
                "shared_expertise": sorted(overlap_tags),
                "shared_decisions": shared_decision_count,
            },
            "unique_strengths": {
                "team_a_only": sorted(unique_a),
                "team_b_only": sorted(unique_b),
            },
            "synergies": synergies,
            "integration_risks": integration_risks,
            "combined_expertise_coverage": sorted(team_a_tags | team_b_tags),
        }

    # ------------------------------------------------------------------
    # Knowledge map
    # ------------------------------------------------------------------

    def _build_knowledge_map(self, db: Session) -> dict:
        """Map topics to their artifact, member, and decision counts."""
        # Collect all topics from contributions
        contributions = db.query(ContributionRecord).all()
        topic_artifacts: dict[str, set[str]] = defaultdict(set)
        topic_members: dict[str, set[str]] = defaultdict(set)

        for c in contributions:
            topics = c.topics if isinstance(c.topics, list) else []
            for topic in topics:
                if c.artifact_id:
                    topic_artifacts[topic].add(c.artifact_id)
                if c.member_id:
                    topic_members[topic].add(c.member_id)

        # Collect topics from decisions
        decisions = db.query(DecisionRecord).all()
        topic_decisions: dict[str, int] = Counter()
        for d in decisions:
            tags = d.tags if isinstance(d.tags, list) else []
            for tag in tags:
                topic_decisions[tag] += 1

        # Also gather topics from member expertise tags
        members = db.query(MemberRecord).filter(MemberRecord.status == "active").all()
        for m in members:
            tags = m.expertise_tags if isinstance(m.expertise_tags, list) else []
            for tag in tags:
                topic_members[tag].add(m.id)

        # Combine all topic names
        all_topics = set(topic_artifacts.keys()) | set(topic_members.keys()) | set(topic_decisions.keys())

        topic_list = []
        for topic in sorted(all_topics):
            topic_list.append({
                "name": topic,
                "artifact_count": len(topic_artifacts.get(topic, set())),
                "member_count": len(topic_members.get(topic, set())),
                "decision_count": topic_decisions.get(topic, 0),
            })

        # Coverage score: percentage of topics that have at least 2 members and 1 artifact
        well_covered = sum(
            1 for t in topic_list
            if t["member_count"] >= 2 and t["artifact_count"] >= 1
        )
        coverage_score = (well_covered / len(topic_list) * 100) if topic_list else 0.0

        return {
            "topics": topic_list,
            "coverage_score": round(coverage_score, 1),
        }

    # ------------------------------------------------------------------
    # Team dynamics
    # ------------------------------------------------------------------

    def _analyze_team_dynamics(self, db: Session) -> dict:
        """Analyze collaboration patterns and knowledge distribution."""
        members = db.query(MemberRecord).filter(MemberRecord.status == "active").all()

        if not members:
            return {
                "collaboration_density": 0.0,
                "knowledge_distribution": {"gini_coefficient": 0.0, "interpretation": "No data"},
                "key_connectors": [],
                "isolated_members": [],
            }

        # Collaboration density: how many members share artifacts
        # Build a co-contribution graph
        artifact_contributors: dict[str, set[str]] = defaultdict(set)
        contributions = (
            db.query(ContributionRecord)
            .filter(ContributionRecord.artifact_id.isnot(None))
            .all()
        )
        for c in contributions:
            artifact_contributors[c.artifact_id].add(c.member_id)

        # Count connections (pairs of members who co-contributed)
        connections: dict[str, set[str]] = defaultdict(set)
        for _artifact_id, contributor_ids in artifact_contributors.items():
            contributors = list(contributor_ids)
            for i in range(len(contributors)):
                for j in range(i + 1, len(contributors)):
                    connections[contributors[i]].add(contributors[j])
                    connections[contributors[j]].add(contributors[i])

        member_ids = {m.id for m in members}
        total_possible_edges = len(members) * (len(members) - 1) / 2 if len(members) > 1 else 1
        actual_edges = sum(len(peers & member_ids) for mid, peers in connections.items() if mid in member_ids) / 2
        collaboration_density = actual_edges / total_possible_edges if total_possible_edges > 0 else 0.0

        # Knowledge distribution (Gini of contribution counts)
        contribution_counts = [int(m.total_contributions or 0) for m in members]
        gini = self._gini_coefficient(contribution_counts)

        if gini < 0.3:
            interpretation = "Well distributed — knowledge is shared fairly evenly"
        elif gini < 0.5:
            interpretation = "Moderately concentrated — some members contribute significantly more"
        elif gini < 0.7:
            interpretation = "Highly concentrated — a few members dominate contributions"
        else:
            interpretation = "Extremely concentrated — knowledge is siloed in very few people"

        # Key connectors: members with the most co-contribution connections
        name_map = {m.id: m.name for m in members}
        key_connectors = []
        for mid in sorted(connections.keys(), key=lambda x: len(connections[x] & member_ids), reverse=True)[:5]:
            if mid in member_ids:
                key_connectors.append({
                    "member_id": mid,
                    "name": name_map.get(mid, "Unknown"),
                    "connection_count": len(connections[mid] & member_ids),
                })

        # Isolated members: active members with zero connections
        connected_ids = {mid for mid in connections if connections[mid] & member_ids}
        isolated = [
            {"member_id": m.id, "name": m.name}
            for m in members
            if m.id not in connected_ids
        ]

        return {
            "collaboration_density": round(collaboration_density, 3),
            "knowledge_distribution": {
                "gini_coefficient": round(gini, 3),
                "interpretation": interpretation,
            },
            "key_connectors": key_connectors,
            "isolated_members": isolated,
        }

    # ------------------------------------------------------------------
    # Decision patterns
    # ------------------------------------------------------------------

    def _analyze_decision_patterns(self, db: Session, now: datetime) -> dict:
        """Analyze decision-making patterns."""
        decisions = db.query(DecisionRecord).all()

        if not decisions:
            return {
                "total_decisions": 0,
                "by_type": {},
                "avg_decision_makers": 0.0,
                "decision_velocity": {"decisions_per_week": 0.0, "trend": "no_data"},
                "most_active_decision_makers": [],
            }

        # By type
        by_type: Counter = Counter()
        for d in decisions:
            by_type[d.decision_type or "unknown"] += 1

        # Average decision makers
        maker_counts = []
        member_counter: Counter = Counter()
        for d in decisions:
            involved = d.involved_member_ids if isinstance(d.involved_member_ids, list) else []
            maker_counts.append(len(involved))
            for mid in involved:
                member_counter[mid] += 1

        avg_makers = sum(maker_counts) / len(maker_counts) if maker_counts else 0.0

        # Decision velocity: decisions per week over the last 8 weeks
        eight_weeks_ago = now - timedelta(weeks=8)
        four_weeks_ago = now - timedelta(weeks=4)

        recent_decisions = [
            d for d in decisions
            if d.created_at and d.created_at >= eight_weeks_ago
        ]
        last_4_weeks = [
            d for d in decisions
            if d.created_at and d.created_at >= four_weeks_ago
        ]
        prev_4_weeks = [
            d for d in decisions
            if d.created_at and eight_weeks_ago <= d.created_at < four_weeks_ago
        ]

        velocity = len(recent_decisions) / 8.0 if recent_decisions else 0.0

        if len(last_4_weeks) > len(prev_4_weeks):
            trend = "accelerating"
        elif len(last_4_weeks) < len(prev_4_weeks):
            trend = "decelerating"
        else:
            trend = "stable"

        # Most active decision makers
        members_in_decisions = (
            db.query(MemberRecord)
            .filter(MemberRecord.id.in_(list(member_counter.keys())))
            .all()
            if member_counter else []
        )
        name_map = {m.id: m.name for m in members_in_decisions}

        most_active = [
            {
                "member_id": mid,
                "name": name_map.get(mid, "Unknown"),
                "count": count,
            }
            for mid, count in member_counter.most_common(5)
        ]

        return {
            "total_decisions": len(decisions),
            "by_type": dict(by_type),
            "avg_decision_makers": round(avg_makers, 1),
            "decision_velocity": {
                "decisions_per_week": round(velocity, 2),
                "trend": trend,
            },
            "most_active_decision_makers": most_active,
        }

    # ------------------------------------------------------------------
    # Risk profile
    # ------------------------------------------------------------------

    def _analyze_risk_profile(self, db: Session) -> dict:
        """Analyze organizational risk factors."""
        members = db.query(MemberRecord).filter(MemberRecord.status == "active").all()

        if not members:
            return {
                "bus_factor_members": [],
                "knowledge_silos": [],
                "single_point_failures": 0,
                "overall_resilience_score": 0.0,
            }

        # Build tag-to-member mapping
        tag_members: dict[str, list[str]] = defaultdict(list)
        for m in members:
            tags = m.expertise_tags if isinstance(m.expertise_tags, list) else []
            for tag in tags:
                tag_members[tag].append(m.name)

        # Knowledge silos: tags with only one member
        knowledge_silos = [tag for tag, names in tag_members.items() if len(names) == 1]

        # Bus factor members: members who are sole experts in any area
        bus_factor_names: set[str] = set()
        for tag in knowledge_silos:
            bus_factor_names.update(tag_members[tag])

        # Single point of failure: artifacts with only one contributor
        contributions = (
            db.query(ContributionRecord)
            .filter(ContributionRecord.artifact_id.isnot(None))
            .all()
        )
        artifact_contributors: dict[str, set[str]] = defaultdict(set)
        for c in contributions:
            artifact_contributors[c.artifact_id].add(c.member_id)

        single_point_artifacts = sum(
            1 for contributors in artifact_contributors.values()
            if len(contributors) == 1
        )

        # Overall resilience score (0-100)
        # Penalize for silos, bus factor members, and single-point artifacts
        total_tags = len(tag_members) if tag_members else 1
        total_artifacts = len(artifact_contributors) if artifact_contributors else 1

        silo_ratio = len(knowledge_silos) / total_tags
        spf_ratio = single_point_artifacts / total_artifacts

        resilience = 100.0
        resilience -= silo_ratio * 40  # Up to -40 for all-silo tags
        resilience -= spf_ratio * 30   # Up to -30 for all single-contributor artifacts
        resilience -= min(20.0, len(bus_factor_names) * 5.0)  # Up to -20 for bus factor people
        if len(members) <= 2:
            resilience -= 10  # Small team penalty
        resilience = max(0.0, min(100.0, resilience))

        return {
            "bus_factor_members": sorted(bus_factor_names),
            "knowledge_silos": sorted(knowledge_silos),
            "single_point_failures": single_point_artifacts,
            "overall_resilience_score": round(resilience, 1),
        }

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_recommendations(
        summary: dict,
        knowledge_map: dict,
        team_dynamics: dict,
        decision_patterns: dict,
        risk_profile: dict,
    ) -> list[str]:
        """Generate actionable recommendations based on analysis findings."""
        recs: list[str] = []

        # Knowledge coverage
        coverage = knowledge_map.get("coverage_score", 0)
        if coverage < 50:
            recs.append(
                f"Knowledge coverage is only {coverage}%. "
                "Many topics lack sufficient documentation or cross-trained members. "
                "Prioritize knowledge-sharing sessions for poorly covered areas."
            )

        # Collaboration density
        density = team_dynamics.get("collaboration_density", 0)
        if density < 0.3:
            recs.append(
                f"Collaboration density is low ({density:.1%}). "
                "Encourage cross-functional projects, pair work, and shared reviews."
            )

        # Knowledge distribution
        gini = team_dynamics.get("knowledge_distribution", {}).get("gini_coefficient", 0)
        if gini > 0.5:
            recs.append(
                f"Knowledge is heavily concentrated (Gini: {gini:.2f}). "
                "Balance workload distribution and create mentoring programs."
            )

        # Isolated members
        isolated = team_dynamics.get("isolated_members", [])
        if isolated:
            names = ", ".join(m["name"] for m in isolated[:3])
            recs.append(
                f"{len(isolated)} member(s) are isolated (no co-contributions): {names}. "
                "Pair them with active collaborators."
            )

        # Decision patterns
        avg_makers = decision_patterns.get("avg_decision_makers", 0)
        if avg_makers < 2 and decision_patterns.get("total_decisions", 0) > 0:
            recs.append(
                f"Decisions average only {avg_makers:.1f} participants. "
                "Broaden decision-making to reduce key-person dependency."
            )

        velocity = decision_patterns.get("decision_velocity", {})
        if velocity.get("trend") == "decelerating":
            recs.append(
                "Decision velocity is declining. Review if bottlenecks or unclear ownership are causing delays."
            )

        # Risk profile
        silos = risk_profile.get("knowledge_silos", [])
        if silos:
            silo_sample = ", ".join(silos[:5])
            recs.append(
                f"{len(silos)} knowledge silo(s) detected: {silo_sample}. "
                "Cross-train team members to eliminate single points of failure."
            )

        spf = risk_profile.get("single_point_failures", 0)
        if spf > 0:
            recs.append(
                f"{spf} artifact(s) have only a single contributor. "
                "Assign backup contributors or reviewers."
            )

        resilience = risk_profile.get("overall_resilience_score", 100)
        if resilience < 50:
            recs.append(
                f"Overall resilience score is {resilience}/100 — this is concerning. "
                "Prioritize knowledge distribution and documentation."
            )

        if not recs:
            recs.append(
                "The organization appears healthy across all measured dimensions. "
                "Continue current practices and re-run this analysis periodically."
            )

        return recs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _gini_coefficient(values: list[int]) -> float:
        """Calculate the Gini coefficient for a list of values."""
        if not values or all(v == 0 for v in values):
            return 0.0

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        total = sum(sorted_vals)

        if total == 0:
            return 0.0

        weighted_sum = 0.0
        for i, val in enumerate(sorted_vals):
            weighted_sum += (2 * (i + 1) - n - 1) * val

        gini = weighted_sum / (n * total)
        return max(0.0, min(1.0, gini))
