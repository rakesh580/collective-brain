"""Onboarding Service — auto-generates knowledge briefings for new team members."""

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.artifact import ArtifactRecord
from app.models.contribution import ContributionRecord
from app.models.decision import DecisionRecord, RiskAlert
from app.models.knowledge_embedding import KnowledgeEmbedding
from app.models.member import MemberRecord
from app.services.llm_service import LLMService

logger = logging.getLogger("collective_brain.onboarding")

BRIEFING_PROMPT = """You are an expert at creating onboarding briefings for new team members.
Given the following organizational data, create a structured briefing document.

TEAM MEMBERS:
{members_section}

KEY DECISIONS:
{decisions_section}

KNOWLEDGE SOURCES:
{sources_section}

ACTIVE RISKS:
{risks_section}

{topic_filter}

Create a briefing with these sections (return as JSON):
{{
  "team_overview": {{
    "content": "A 2-3 paragraph overview of the team, their expertise areas, and how they collaborate",
    "key_facts": ["fact1", "fact2", "..."]
  }},
  "key_decisions": {{
    "content": "Summary of the most important decisions and their impact",
    "highlights": ["highlight1", "highlight2"]
  }},
  "knowledge_architecture": {{
    "content": "Overview of what knowledge exists, how it's organized, and where to find things",
    "tips": ["tip1", "tip2"]
  }},
  "active_risks": {{
    "content": "Current risks and things to watch out for",
    "action_items": ["item1", "item2"]
  }},
  "getting_started": {{
    "content": "Practical advice for getting up to speed quickly",
    "action_items": ["item1", "item2", "item3"]
  }}
}}

Return ONLY valid JSON, no other text."""


class OnboardingService:
    """Generates knowledge briefings for new team members."""

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_briefing(
        self,
        db: Session,
        member_id: str | None = None,
        topics: list[str] | None = None,
    ) -> dict:
        """Generate a comprehensive onboarding briefing.

        Gathers key decisions, active members, knowledge architecture,
        current risks, and synthesises into a readable briefing via LLM.
        """
        # 1. Gather team members
        members = (
            db.query(MemberRecord)
            .filter(MemberRecord.status == "active")
            .order_by(MemberRecord.total_contributions.desc())
            .all()
        )

        # 2. Gather key decisions (most recent + highest confidence)
        decisions_query = db.query(DecisionRecord).order_by(
            DecisionRecord.decided_at.desc().nullslast(),
            DecisionRecord.confidence_score.desc(),
        )
        if topics:
            # Filter decisions by topic if specified
            decisions = [
                d for d in decisions_query.limit(50).all()
                if self._matches_topics(d, topics)
            ][:15]
        else:
            decisions = decisions_query.limit(15).all()

        # 3. Knowledge architecture — artifact summary
        source_type_counts = (
            db.query(
                ArtifactRecord.source_type,
                func.count(ArtifactRecord.id).label("cnt"),
            )
            .group_by(ArtifactRecord.source_type)
            .all()
        )
        total_chunks = db.query(func.count(KnowledgeEmbedding.id)).scalar() or 0
        total_artifacts = db.query(func.count(ArtifactRecord.id)).scalar() or 0

        # 4. Active risks
        active_risks = (
            db.query(RiskAlert)
            .filter(RiskAlert.is_resolved == False)  # noqa: E712
            .order_by(RiskAlert.detected_at.desc())
            .limit(10)
            .all()
        )

        # 5. If a specific member, find their areas of interest
        target_member = None
        if member_id:
            target_member = db.query(MemberRecord).filter(MemberRecord.id == member_id).first()

        # 6. Recommended reading — most-contributed artifacts
        recommended_artifacts = (
            db.query(
                ArtifactRecord.id,
                ArtifactRecord.title,
                ArtifactRecord.source_type,
                func.count(ContributionRecord.id).label("contribution_count"),
            )
            .outerjoin(ContributionRecord, ContributionRecord.artifact_id == ArtifactRecord.id)
            .group_by(ArtifactRecord.id, ArtifactRecord.title, ArtifactRecord.source_type)
            .order_by(func.count(ContributionRecord.id).desc())
            .limit(5)
            .all()
        )

        # Build prompt sections
        members_section = self._format_members(members)
        decisions_section = self._format_decisions(decisions)
        sources_section = self._format_sources(source_type_counts, total_artifacts, total_chunks)
        risks_section = self._format_risks(active_risks)
        topic_filter = ""
        if topics:
            topic_filter = f"Focus the briefing on these topics: {', '.join(topics)}"
        elif target_member:
            topic_filter = f"This briefing is for {target_member.name}. Tailor recommendations accordingly."

        prompt = BRIEFING_PROMPT.format(
            members_section=members_section,
            decisions_section=decisions_section,
            sources_section=sources_section,
            risks_section=risks_section,
            topic_filter=topic_filter,
        )

        # Call LLM
        messages = [
            {"role": "system", "content": "You are an onboarding assistant. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ]

        try:
            raw_response = await self.llm.generate(messages, max_tokens=4096)
            parsed = self._parse_llm_response(raw_response)
        except Exception as e:
            logger.error("LLM briefing generation failed: %s", e)
            parsed = self._build_fallback_briefing(members, decisions, active_risks)

        # Assemble final result
        sections = [
            {
                "title": "Team Overview",
                "content": parsed.get("team_overview", {}).get("content", "No data available."),
                "key_facts": parsed.get("team_overview", {}).get("key_facts", []),
            },
            {
                "title": "Key Decisions",
                "content": parsed.get("key_decisions", {}).get("content", "No decisions recorded yet."),
                "decisions": [
                    {"id": d.id, "title": d.title, "type": d.decision_type}
                    for d in decisions[:10]
                ],
            },
            {
                "title": "Knowledge Architecture",
                "content": parsed.get("knowledge_architecture", {}).get("content", ""),
                "sources": [
                    {"type": row.source_type, "count": row.cnt}
                    for row in source_type_counts
                ],
            },
            {
                "title": "Active Risks",
                "content": parsed.get("active_risks", {}).get("content", "No active risks."),
                "risks": [
                    {"id": r.id, "title": r.title, "severity": r.severity}
                    for r in active_risks[:5]
                ],
            },
            {
                "title": "Getting Started",
                "content": parsed.get("getting_started", {}).get("content", ""),
                "action_items": parsed.get("getting_started", {}).get("action_items", []),
            },
        ]

        key_contacts = [
            {
                "name": m.name,
                "expertise": m.expertise_tags if isinstance(m.expertise_tags, list) else [],
                "role_description": (
                    f"Expert in {', '.join(m.expertise_tags[:3])}"
                    if isinstance(m.expertise_tags, list) and m.expertise_tags
                    else "Team member"
                ),
            }
            for m in members[:5]
        ]

        recommended_reading = [
            {
                "artifact_id": row.id,
                "title": row.title or row.id,
                "reason": f"Most contributed {row.source_type} artifact ({row.contribution_count} contributions)",
            }
            for row in recommended_artifacts
            if row.contribution_count and row.contribution_count > 0
        ]

        return {
            "title": "Onboarding Briefing",
            "generated_at": datetime.now(UTC).isoformat(),
            "sections": sections,
            "key_contacts": key_contacts,
            "recommended_reading": recommended_reading,
        }

    async def generate_topic_briefing(self, db: Session, topic: str) -> dict:
        """Generate a briefing focused on a specific topic.

        Returns decisions, members, artifacts, and context related to that topic.
        """
        topic_lower = topic.lower()
        topic_tokens = set(topic_lower.split())

        # Find related decisions
        all_decisions = db.query(DecisionRecord).all()
        related_decisions = [
            d for d in all_decisions
            if self._matches_topics(d, [topic])
        ]

        # Find members with relevant expertise
        all_members = (
            db.query(MemberRecord)
            .filter(MemberRecord.status == "active")
            .all()
        )
        relevant_members = []
        for m in all_members:
            tags = m.expertise_tags if isinstance(m.expertise_tags, list) else []
            tags_lower = {t.lower() for t in tags}
            if tags_lower & topic_tokens or any(topic_lower in t.lower() or t.lower() in topic_lower for t in tags):
                relevant_members.append(m)

        # Find related artifacts via contributions with matching topics
        related_contributions = db.query(ContributionRecord).all()
        related_artifact_ids: set[str] = set()
        for c in related_contributions:
            c_topics = c.topics if isinstance(c.topics, list) else []
            c_topics_lower = {t.lower() for t in c_topics}
            if c_topics_lower & topic_tokens or any(topic_lower in t.lower() for t in c_topics):
                if c.artifact_id:
                    related_artifact_ids.add(c.artifact_id)

        related_artifacts = []
        if related_artifact_ids:
            related_artifacts = (
                db.query(ArtifactRecord)
                .filter(ArtifactRecord.id.in_(list(related_artifact_ids)))
                .all()
            )

        # Find knowledge chunks mentioning the topic
        chunk_count = (
            db.query(func.count(KnowledgeEmbedding.id))
            .filter(KnowledgeEmbedding.content.ilike(f"%{topic}%"))
            .scalar()
            or 0
        )

        return {
            "topic": topic,
            "generated_at": datetime.now(UTC).isoformat(),
            "decisions": [
                {
                    "id": d.id,
                    "title": d.title,
                    "description": d.description,
                    "decision_type": d.decision_type,
                    "status": d.status,
                    "decided_at": d.decided_at.isoformat() if d.decided_at else None,
                }
                for d in related_decisions[:10]
            ],
            "members": [
                {
                    "id": m.id,
                    "name": m.name,
                    "expertise_tags": m.expertise_tags if isinstance(m.expertise_tags, list) else [],
                }
                for m in relevant_members
            ],
            "artifacts": [
                {
                    "id": a.id,
                    "title": a.title or a.id,
                    "source_type": a.source_type,
                }
                for a in related_artifacts[:10]
            ],
            "knowledge_chunk_count": chunk_count,
            "summary": (
                f"Found {len(related_decisions)} decision(s), "
                f"{len(relevant_members)} member(s), "
                f"{len(related_artifacts)} artifact(s), and "
                f"{chunk_count} knowledge chunk(s) related to '{topic}'."
            ),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _matches_topics(decision: DecisionRecord, topics: list[str]) -> bool:
        """Check if a decision relates to any of the given topics."""
        topics_lower = {t.lower() for t in topics}
        tags = decision.tags if isinstance(decision.tags, list) else []
        tags_lower = {t.lower() for t in tags}

        if tags_lower & topics_lower:
            return True

        title = (decision.title or "").lower()
        desc = (decision.description or "").lower()
        context = (decision.context_summary or "").lower()

        for topic in topics_lower:
            tokens = topic.split()
            for token in tokens:
                if len(token) > 2 and (token in title or token in desc or token in context):
                    return True
        return False

    @staticmethod
    def _format_members(members: list[MemberRecord]) -> str:
        if not members:
            return "No active team members found."
        lines = []
        for m in members[:10]:
            tags = m.expertise_tags if isinstance(m.expertise_tags, list) else []
            expertise = ", ".join(tags[:5]) if tags else "Not specified"
            contributions = int(m.total_contributions or 0)
            lines.append(f"- {m.name}: expertise in [{expertise}], {contributions} contributions")
        return "\n".join(lines)

    @staticmethod
    def _format_decisions(decisions: list[DecisionRecord]) -> str:
        if not decisions:
            return "No decisions recorded yet."
        lines = []
        for d in decisions[:10]:
            date_str = d.decided_at.strftime("%Y-%m-%d") if d.decided_at else "Unknown date"
            lines.append(f"- [{d.decision_type}] {d.title} ({date_str}): {d.description or 'No description'}")
        return "\n".join(lines)

    @staticmethod
    def _format_sources(source_counts, total_artifacts: int, total_chunks: int) -> str:
        if not source_counts:
            return "No knowledge sources ingested yet."
        lines = [f"Total: {total_artifacts} artifacts, {total_chunks} knowledge chunks"]
        for row in source_counts:
            lines.append(f"- {row.source_type}: {row.cnt} artifact(s)")
        return "\n".join(lines)

    @staticmethod
    def _format_risks(risks: list) -> str:
        if not risks:
            return "No active risks detected."
        lines = []
        for r in risks[:5]:
            lines.append(f"- [{r.severity}] {r.title}: {r.description or 'No description'}")
        return "\n".join(lines)

    @staticmethod
    def _parse_llm_response(raw_response: str) -> dict:
        """Parse LLM JSON response into a dict."""
        text = raw_response.strip()

        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start: end + 1])
                except json.JSONDecodeError:
                    pass

        logger.warning("Failed to parse LLM briefing response, using fallback")
        return {}

    @staticmethod
    def _build_fallback_briefing(
        members: list[MemberRecord],
        decisions: list[DecisionRecord],
        risks: list,
    ) -> dict:
        """Build a basic briefing when LLM is unavailable."""
        member_names = [m.name for m in members[:5]]
        decision_titles = [d.title for d in decisions[:5]]

        return {
            "team_overview": {
                "content": (
                    f"The team has {len(members)} active member(s). "
                    f"Key contributors include: {', '.join(member_names) if member_names else 'none yet'}."
                ),
                "key_facts": [
                    f"{len(members)} active team members",
                    f"{len(decisions)} key decisions on record",
                ],
            },
            "key_decisions": {
                "content": (
                    f"There are {len(decisions)} recorded decisions. "
                    f"Recent ones include: {', '.join(decision_titles) if decision_titles else 'none yet'}."
                ),
                "highlights": decision_titles[:3],
            },
            "knowledge_architecture": {
                "content": "Knowledge is stored as ingested artifacts with associated embeddings.",
                "tips": ["Review the most-contributed artifacts first"],
            },
            "active_risks": {
                "content": f"There are {len(risks)} active risk alert(s).",
                "action_items": [r.title for r in risks[:3]] if risks else ["No active risks"],
            },
            "getting_started": {
                "content": "Start by reviewing key decisions and connecting with top contributors.",
                "action_items": [
                    "Review the key decisions listed above",
                    "Introduce yourself to the key contacts",
                    "Read the recommended artifacts",
                ],
            },
        }
