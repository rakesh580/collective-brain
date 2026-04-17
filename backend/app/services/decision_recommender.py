"""Decision Recommender — recommends who should be involved in making a decision."""

import logging
from collections import Counter, defaultdict
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.contribution import ContributionRecord
from app.models.decision import DecisionRecord
from app.models.member import MemberRecord

logger = logging.getLogger("collective_brain.decision_recommender")


class DecisionRecommenderService:
    """Recommends who should be involved in making a decision."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recommend_decision_makers(
        self,
        db: Session,
        topic: str,
        decision_type: str = "technical",
        top_k: int = 5,
    ) -> dict:
        """Find the best people to make a decision about a topic.

        Scoring factors:
        1. Expertise match: members whose expertise_tags overlap with the topic (weight: 40%)
        2. Past decision involvement: members involved in related past decisions (weight: 30%)
        3. Contribution recency: recently active members scored higher (weight: 15%)
        4. Contribution breadth: members who contributed across multiple artifacts (weight: 15%)
        """
        topic_lower = topic.lower()
        topic_tokens = set(topic_lower.split())

        members = (
            db.query(MemberRecord)
            .filter(MemberRecord.status == "active")
            .all()
        )

        if not members:
            return {
                "topic": topic,
                "decision_type": decision_type,
                "recommended_members": [],
                "suggested_reviewers": [],
                "knowledge_gaps": [topic],
            }

        # Gather related decisions (matching tags or title/description keywords)
        all_decisions = db.query(DecisionRecord).all()
        related_decisions = self._find_related_decisions(all_decisions, topic_lower, topic_tokens)

        # Build member-to-decision involvement map
        member_decisions: dict[str, list[DecisionRecord]] = defaultdict(list)
        for dec in related_decisions:
            involved = dec.involved_member_ids if isinstance(dec.involved_member_ids, list) else []
            for mid in involved:
                member_decisions[mid].append(dec)

        # Contribution breadth: distinct artifact count per member
        breadth_rows = (
            db.query(
                ContributionRecord.member_id,
                func.count(func.distinct(ContributionRecord.artifact_id)).label("artifact_count"),
            )
            .filter(ContributionRecord.artifact_id.isnot(None))
            .group_by(ContributionRecord.member_id)
            .all()
        )
        breadth_map: dict[str, int] = {row.member_id: row.artifact_count for row in breadth_rows}
        max_breadth = max(breadth_map.values()) if breadth_map else 1

        now = datetime.now(UTC)
        scored_members: list[dict] = []
        all_expertise_tags: set[str] = set()

        for member in members:
            reasons: list[str] = []
            tags = member.expertise_tags if isinstance(member.expertise_tags, list) else []
            all_expertise_tags.update(tags)

            # --- Factor 1: Expertise match (0-40) ---
            overlap = self._compute_tag_overlap(tags, topic_lower, topic_tokens)
            expertise_score = min(40.0, len(overlap) * 15.0) if overlap else 0.0
            if overlap:
                reasons.append(f"Expert in {', '.join(overlap)}")

            # Also check expertise_scores dict for weighted matching
            scores_dict = member.expertise_scores if isinstance(member.expertise_scores, dict) else {}
            for tag_key, score_val in scores_dict.items():
                if tag_key.lower() in topic_tokens or topic_lower in tag_key.lower():
                    bonus = min(10.0, float(score_val) * 5.0)
                    expertise_score = min(40.0, expertise_score + bonus)
                    if tag_key not in overlap:
                        overlap.append(tag_key)
                        reasons.append(f"High expertise score in {tag_key}")

            # --- Factor 2: Past decision involvement (0-30) ---
            member_related = member_decisions.get(member.id, [])
            decision_score = min(30.0, len(member_related) * 10.0)
            if member_related:
                reasons.append(
                    f"Involved in {len(member_related)} related decision(s)"
                )

            # --- Factor 3: Contribution recency (0-15) ---
            recency_score = 0.0
            if member.last_active:
                last_active = member.last_active
                if last_active.tzinfo is None:
                    last_active = last_active.replace(tzinfo=UTC)
                days_ago = (now - last_active).days
                if days_ago <= 7:
                    recency_score = 15.0
                    reasons.append("Active in the last week")
                elif days_ago <= 14:
                    recency_score = 12.0
                    reasons.append("Active in the last 2 weeks")
                elif days_ago <= 30:
                    recency_score = 8.0
                elif days_ago <= 60:
                    recency_score = 4.0

            # --- Factor 4: Contribution breadth (0-15) ---
            member_breadth = breadth_map.get(member.id, 0)
            breadth_score = (member_breadth / max_breadth) * 15.0 if max_breadth > 0 else 0.0
            if member_breadth >= 3:
                reasons.append(f"Contributed to {member_breadth} artifacts")

            total_score = expertise_score + decision_score + recency_score + breadth_score

            if total_score > 0:
                relevant_decs = [
                    {"id": d.id, "title": d.title} for d in member_related[:5]
                ]
                scored_members.append({
                    "member_id": member.id,
                    "member_name": member.name,
                    "score": round(total_score, 2),
                    "reasons": reasons,
                    "relevant_decisions": relevant_decs,
                    "expertise_overlap": overlap,
                })

        # Sort by score descending
        scored_members.sort(key=lambda m: m["score"], reverse=True)

        recommended = scored_members[:top_k]
        reviewers = scored_members[top_k: top_k + 3]

        # Knowledge gaps: topic tokens that no member has expertise in
        knowledge_gaps = self._find_knowledge_gaps(topic_tokens, all_expertise_tags)

        return {
            "topic": topic,
            "decision_type": decision_type,
            "recommended_members": recommended,
            "suggested_reviewers": reviewers,
            "knowledge_gaps": knowledge_gaps,
        }

    def get_decision_influence_map(self, db: Session) -> dict:
        """Map who actually influences decisions in the org.

        Returns influencers, decision distribution, and concentration score.
        """
        decisions = db.query(DecisionRecord).all()

        if not decisions:
            return {
                "influencers": [],
                "decision_distribution": {},
                "concentration_score": 0.0,
            }

        member_decision_count: Counter = Counter()
        member_topics: dict[str, set[str]] = defaultdict(set)

        for dec in decisions:
            involved = dec.involved_member_ids if isinstance(dec.involved_member_ids, list) else []
            tags = dec.tags if isinstance(dec.tags, list) else []
            for mid in involved:
                member_decision_count[mid] += 1
                member_topics[mid].update(tags)

        if not member_decision_count:
            return {
                "influencers": [],
                "decision_distribution": {},
                "concentration_score": 0.0,
            }

        # Resolve member names
        member_ids = list(member_decision_count.keys())
        members = (
            db.query(MemberRecord)
            .filter(MemberRecord.id.in_(member_ids))
            .all()
        )
        name_map = {m.id: m.name for m in members}

        influencers = []
        for mid, count in member_decision_count.most_common():
            influencers.append({
                "member_id": mid,
                "member_name": name_map.get(mid, "Unknown"),
                "decision_count": count,
                "topics": sorted(member_topics.get(mid, set())),
            })

        distribution = {mid: count for mid, count in member_decision_count.items()}

        # Gini coefficient for concentration
        concentration = self._gini_coefficient(list(member_decision_count.values()))

        return {
            "influencers": influencers,
            "decision_distribution": distribution,
            "concentration_score": round(concentration, 3),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_related_decisions(
        decisions: list[DecisionRecord],
        topic_lower: str,
        topic_tokens: set[str],
    ) -> list[DecisionRecord]:
        """Find decisions related to the given topic by tag/title/description matching."""
        related = []
        for dec in decisions:
            tags = dec.tags if isinstance(dec.tags, list) else []
            tags_lower = {t.lower() for t in tags}

            # Check tag overlap
            if tags_lower & topic_tokens:
                related.append(dec)
                continue

            # Check title/description keyword match
            title = (dec.title or "").lower()
            desc = (dec.description or "").lower()
            if any(token in title or token in desc for token in topic_tokens if len(token) > 2):
                related.append(dec)
                continue

            # Check if topic appears in context
            context = (dec.context_summary or "").lower()
            if topic_lower in context:
                related.append(dec)

        return related

    @staticmethod
    def _compute_tag_overlap(
        member_tags: list[str],
        topic_lower: str,
        topic_tokens: set[str],
    ) -> list[str]:
        """Find which of a member's expertise tags overlap with the topic."""
        overlap = []
        for tag in member_tags:
            tag_lower = tag.lower()
            # Direct token match
            if tag_lower in topic_tokens or tag_lower in topic_lower or topic_lower in tag_lower or any(token in tag_lower for token in topic_tokens if len(token) > 2):
                overlap.append(tag)
        return overlap

    @staticmethod
    def _find_knowledge_gaps(topic_tokens: set[str], all_expertise_tags: set[str]) -> list[str]:
        """Identify topic tokens that no member has expertise in."""
        all_tags_lower = {t.lower() for t in all_expertise_tags}
        gaps = []
        for token in topic_tokens:
            if len(token) <= 2:
                continue  # Skip short words like "in", "to", etc.
            found = any(
                token in tag or tag in token
                for tag in all_tags_lower
            )
            if not found:
                gaps.append(token)
        return gaps

    @staticmethod
    def _gini_coefficient(values: list[int]) -> float:
        """Calculate the Gini coefficient for a list of values.

        Returns 0.0 for perfect equality, 1.0 for maximum inequality.
        """
        if not values or all(v == 0 for v in values):
            return 0.0

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        total = sum(sorted_vals)

        if total == 0:
            return 0.0

        cumulative = 0.0
        weighted_sum = 0.0
        for i, val in enumerate(sorted_vals):
            cumulative += val
            weighted_sum += (2 * (i + 1) - n - 1) * val

        gini = weighted_sum / (n * total)
        return max(0.0, min(1.0, gini))
