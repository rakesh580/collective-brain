"""
Agent tools for the Collective Brain LangGraph agent.

Each tool is a thin wrapper around existing service methods,
exposing them for the LLM to call autonomously.
"""

import json
from datetime import datetime, timedelta
from typing import Optional

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.models.member import MemberRecord
from app.models.contribution import ContributionRecord
from app.models.insight import InsightRecord
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStoreService
from app.services.memory_graph import MemoryGraph


def create_tools(db: Session, embedder: EmbeddingService, vector_store: VectorStoreService, room_id: str | None = None):
    """Create all agent tools with the shared db/embedder/vector_store context."""

    @tool
    def search_knowledge(query: str, top_k: int = 8) -> str:
        """Search the team's collective knowledge base using semantic similarity.
        Use this to find relevant information from ingested documents, chat history,
        code commits, and task records. Returns the most relevant text chunks."""
        embedding = embedder.embed(query)
        results = vector_store.query(query_embedding=embedding, n_results=top_k, room_id=room_id)

        if not results["documents"] or not results["documents"][0]:
            return "No relevant knowledge found for this query."

        output = []
        docs = results["documents"][0]
        metas = results["metadatas"][0] if results["metadatas"] else [{}] * len(docs)
        distances = results["distances"][0] if results["distances"] else [0.0] * len(docs)

        for doc, meta, dist in zip(docs, metas, distances):
            source = meta.get("source_type", "unknown")
            author = meta.get("author", "unknown")
            ref = meta.get("source_ref", "")
            score = round(1 - dist, 2)
            output.append(f"[{source}] (by {author}, ref: {ref}, relevance: {score})\n{doc[:500]}")

        return "\n\n---\n\n".join(output)

    @tool
    def get_member_profile(name_or_id: str) -> str:
        """Get detailed profile of a team member including their expertise areas,
        contribution count, and expertise scores. Use this when you need to understand
        what a specific person knows or has worked on."""
        # Try by ID first, then by name (case-insensitive)
        member = db.query(MemberRecord).filter(MemberRecord.id == name_or_id).first()
        if not member:
            member = (
                db.query(MemberRecord)
                .filter(MemberRecord.name.ilike(f"%{name_or_id}%"))
                .first()
            )
        if not member:
            return f"No member found matching '{name_or_id}'."

        # Compute expertise scores
        graph = MemoryGraph(db, room_id=room_id)
        scores = graph.compute_expertise_scores(member.id)

        profile = {
            "name": member.name,
            "id": member.id,
            "email": member.email,
            "expertise_tags": member.expertise_tags or [],
            "expertise_scores": scores,
            "total_contributions": member.total_contributions or 0,
            "last_active": member.last_active.isoformat() if member.last_active else "unknown",
            "aliases": member.aliases or [],
        }
        return json.dumps(profile, indent=2)

    @tool
    def list_team_members() -> str:
        """List all team members with their basic info, expertise tags, and contribution counts.
        Use this to get an overview of the entire team."""
        members = db.query(MemberRecord).order_by(MemberRecord.name).all()
        if not members:
            return "No team members found. The knowledge base may be empty."

        output = []
        for m in members:
            tags = ", ".join(m.expertise_tags or [])
            output.append(
                f"- {m.name} (id: {m.id}): {int(m.total_contributions or 0)} contributions, "
                f"expertise: [{tags}], last active: {m.last_active.strftime('%Y-%m-%d') if m.last_active else 'unknown'}"
            )
        return "\n".join(output)

    @tool
    def find_experts(topic: str) -> str:
        """Find team members who have expertise in a specific topic.
        Returns members connected to the topic in the knowledge graph with their
        contribution counts. Use this when recommending someone for a task."""
        graph = MemoryGraph(db, room_id=room_id)
        nodes, edges = graph.get_topic_subgraph(topic)

        if not nodes:
            # Try partial match
            q = db.query(ContributionRecord)
            if room_id:
                q = q.filter(ContributionRecord.room_id == room_id)
            all_contribs = q.all()
            topic_lower = topic.lower()
            matching_members: dict[str, int] = {}
            for c in all_contribs:
                for t in (c.topics or []):
                    if topic_lower in t.lower():
                        matching_members[c.member_id] = matching_members.get(c.member_id, 0) + 1

            if not matching_members:
                return f"No experts found for topic '{topic}'."

            output = [f"Members with expertise related to '{topic}':"]
            for mid, count in sorted(matching_members.items(), key=lambda x: -x[1]):
                member = db.query(MemberRecord).filter(MemberRecord.id == mid).first()
                name = member.name if member else mid
                output.append(f"- {name}: {count} contributions related to this topic")
            return "\n".join(output)

        member_nodes = [n for n in nodes if n.type == "member"]
        topic_edges = [e for e in edges if e.type == "KNOWS_ABOUT"]

        output = [f"Experts for topic '{topic}':"]
        for mn in member_nodes:
            weight = next((e.weight for e in topic_edges if e.source == mn.id), 0)
            output.append(
                f"- {mn.label}: {int(weight)} contributions, "
                f"tags: {mn.properties.get('expertise_tags', [])}"
            )
        return "\n".join(output)

    @tool
    def get_contributions(member_name: str, days: int = 30) -> str:
        """Get recent contributions/activity for a specific team member.
        Returns their commits, messages, documents, and tasks from the specified time period.
        Use this to understand what someone has been working on recently."""
        # Find member
        member = (
            db.query(MemberRecord)
            .filter(MemberRecord.name.ilike(f"%{member_name}%"))
            .first()
        )
        if not member:
            member = db.query(MemberRecord).filter(MemberRecord.id == member_name).first()
        if not member:
            return f"No member found matching '{member_name}'."

        since = datetime.utcnow() - timedelta(days=days)
        q = db.query(ContributionRecord).filter(
            ContributionRecord.member_id == member.id,
            ContributionRecord.timestamp >= since,
        )
        if room_id:
            q = q.filter(ContributionRecord.room_id == room_id)
        contribs = q.order_by(ContributionRecord.timestamp.desc()).limit(30).all()

        if not contribs:
            return f"No contributions found for {member.name} in the last {days} days."

        output = [f"Recent activity for {member.name} (last {days} days, {len(contribs)} contributions):"]
        for c in contribs:
            ts = c.timestamp.strftime("%Y-%m-%d") if c.timestamp else "unknown"
            topics = ", ".join(c.topics or [])
            desc = (c.description or "")[:150]
            output.append(f"- [{c.contribution_type}] {ts}: {desc} (topics: {topics})")
        return "\n".join(output)

    @tool
    def analyze_patterns() -> str:
        """Analyze the team's collaboration patterns to identify risks and insights.
        Detects bus factor risks (single points of failure), siloed members,
        and strong collaboration pairs. Use this for team health assessment."""
        graph = MemoryGraph(db, room_id=room_id)
        patterns = graph.detect_patterns()

        if not patterns:
            return "No significant collaboration patterns detected yet. More data may be needed."

        output = ["Collaboration patterns detected:"]
        for p in patterns:
            members = ", ".join(p.get("related_members", []))
            output.append(
                f"\n**{p['title']}** (type: {p['type']}, confidence: {p.get('confidence', 0):.0%})\n"
                f"{p['body']}\n"
                f"Related members: {members}"
            )
        return "\n".join(output)

    @tool
    def get_topic_network(topic: str) -> str:
        """Get the knowledge graph network around a specific topic.
        Shows which team members are connected to this topic and how they collaborate.
        Use this to understand team structure around a knowledge area."""
        graph = MemoryGraph(db, room_id=room_id)
        nodes, edges = graph.get_topic_subgraph(topic)

        if not nodes:
            return f"No knowledge graph data found for topic '{topic}'."

        output = [f"Knowledge network for '{topic}':"]
        output.append(f"\nNodes ({len(nodes)}):")
        for n in nodes:
            output.append(f"  - [{n.type}] {n.label} (contributions: {n.properties.get('total_contributions', n.properties.get('member_count', 0))})")

        output.append(f"\nConnections ({len(edges)}):")
        for e in edges:
            output.append(f"  - {e.source} --[{e.type}]--> {e.target} (weight: {e.weight})")

        return "\n".join(output)

    @tool
    def get_weekly_summary() -> str:
        """Get the latest weekly team summary with accomplishments and recommendations.
        Returns a cached summary if available, otherwise indicates no summary exists.
        Use this to understand what the team has been doing this week."""
        q = db.query(InsightRecord).filter(InsightRecord.insight_type == "weekly_summary")
        if room_id:
            q = q.filter(InsightRecord.room_id == room_id)
        latest = q.order_by(InsightRecord.generated_at.desc()).first()

        if not latest:
            return "No weekly summary available yet. The team may need to generate one first."

        meta = latest.metadata_json or {}
        highlights = meta.get("highlights", [])
        recommendations = meta.get("recommendations", [])

        output = [
            f"Weekly Summary: {latest.title}",
            f"Generated: {latest.generated_at.strftime('%Y-%m-%d %H:%M') if latest.generated_at else 'unknown'}",
            f"\n{latest.body}",
        ]
        if highlights:
            output.append("\nHighlights:")
            for h in highlights:
                output.append(f"  - {h}")
        if recommendations:
            output.append("\nRecommendations:")
            for r in recommendations:
                output.append(f"  - {r}")
        return "\n".join(output)

    @tool
    def get_recent_activity(days: int = 7) -> str:
        """Get the team-wide recent activity summary for the specified number of days.
        Shows all contributions across the team, grouped by type.
        Use this for an overview of what the whole team has been doing."""
        since = datetime.utcnow() - timedelta(days=days)
        q = db.query(ContributionRecord).filter(ContributionRecord.timestamp >= since)
        if room_id:
            q = q.filter(ContributionRecord.room_id == room_id)
        contribs = q.order_by(ContributionRecord.timestamp.desc()).limit(50).all()

        if not contribs:
            return f"No team activity found in the last {days} days."

        # Group by type
        by_type: dict[str, list] = {}
        for c in contribs:
            ctype = c.contribution_type or "other"
            by_type.setdefault(ctype, []).append(c)

        output = [f"Team activity in the last {days} days ({len(contribs)} contributions):"]
        for ctype, items in sorted(by_type.items()):
            output.append(f"\n{ctype} ({len(items)}):")
            for c in items[:10]:  # Show up to 10 per type
                member = db.query(MemberRecord).filter(MemberRecord.id == c.member_id).first()
                name = member.name if member else c.member_id
                ts = c.timestamp.strftime("%Y-%m-%d") if c.timestamp else "?"
                desc = (c.description or "")[:100]
                output.append(f"  - {ts} {name}: {desc}")
            if len(items) > 10:
                output.append(f"  ... and {len(items) - 10} more")
        return "\n".join(output)

    return [
        search_knowledge,
        get_member_profile,
        list_team_members,
        find_experts,
        get_contributions,
        analyze_patterns,
        get_topic_network,
        get_weekly_summary,
        get_recent_activity,
    ]
