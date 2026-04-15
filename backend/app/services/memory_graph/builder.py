"""Graph construction: cache management, DB queries, NetworkX graph building.

Layers:
  Social   -- Member nodes + COLLABORATED_WITH edges
  Artifact -- ArtifactRecord nodes + CONTRIBUTED_TO edges (member -> artifact)
  Concept  -- Topic nodes + KNOWS_ABOUT / COVERS_TOPIC / HAS_EXPERTISE / DECLARED_SKILL edges
"""

import logging
import math
import time
from collections import defaultdict
from datetime import UTC, datetime

import networkx as nx

from app.models.artifact import ArtifactRecord
from app.models.contribution import ContributionRecord
from app.models.member import MemberRecord
from app.models.user import UserRecord

logger = logging.getLogger("collective_brain.graph")

# Half-life for temporal decay (days).
_HALF_LIFE_DAYS = 180

# Global cached graph -- dict operations are atomic under CPython's GIL
_graph_cache: dict[str | None, "CachedGraph"] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


class CachedGraph:
    """Holds a NetworkX graph and its build timestamp."""

    def __init__(self, G: nx.Graph, built_at: float):
        self.G = G
        self.built_at = built_at

    @property
    def is_stale(self) -> bool:
        return (time.time() - self.built_at) > _CACHE_TTL_SECONDS


def invalidate_graph_cache(room_id: str | None = None):
    """Call after ingestion or member changes to force a rebuild.

    Safe to call from both sync and async contexts -- dict operations
    on CPython are atomic under the GIL.
    """
    if room_id in _graph_cache:
        _graph_cache.pop(room_id, None)
    # Also invalidate the global (None) cache
    if room_id is not None:
        _graph_cache.pop(None, None)


def _ensure_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (UTC). Naive datetimes are assumed UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _temporal_decay(
    timestamp: datetime | None,
    now: datetime | None = None,
    half_life_days: float = _HALF_LIFE_DAYS,
) -> float:
    """Exponential decay weight: 1.0 for *now*, 0.5 at half-life, etc."""
    if timestamp is None:
        return 0.5
    now = now or datetime.now(UTC)
    age_days = max(0, (now - _ensure_aware(timestamp)).total_seconds() / 86400)
    return math.exp(-0.693 * age_days / half_life_days)


def _contribution_type_weight(ctype: str | None) -> float:
    """Assign weight by contribution type -- code weighs more than chat."""
    weights = {
        "git_content": 0.5,
        "slack_content": 0.3,
        "discord_content": 0.3,
        "markdown_content": 0.25,
        "tasks_content": 0.15,
        "document_content": 0.35,
    }
    return weights.get(ctype or "", 0.2)


class GraphBuilderMixin:
    """Mixin providing graph construction, caching, and DB query helpers.

    Expects the host class to set ``self.db`` (SQLAlchemy Session) and
    ``self.room_id`` (str | None).
    """

    # ---- NetworkX Graph Building -----------------------------------------

    def _get_or_build_nx_graph(self) -> nx.Graph:
        """Return cached NetworkX graph or build a fresh one."""
        cached = _graph_cache.get(self.room_id)
        if cached and not cached.is_stale:
            return cached.G

        G = self._build_nx_graph()
        _graph_cache[self.room_id] = CachedGraph(G, time.time())
        return G

    def _build_nx_graph(self) -> nx.Graph:
        """Build a full NetworkX graph from DB data."""
        now = datetime.now(UTC)
        G = nx.Graph()

        members = self._query_members()
        artifacts = self._query_artifacts()
        contribs = self._query_contributions()
        users = self._query_users()

        member_map = {m.id: m for m in members}
        artifact_map = {a.id: a for a in artifacts}

        # Map member -> linked user for skill integration
        member_user_map: dict[str, UserRecord] = {}
        for u in users:
            if u.linked_member_id and u.linked_member_id in member_map:
                member_user_map[u.linked_member_id] = u

        # ---- Member nodes ------------------------------------------------
        for m in members:
            linked_user = member_user_map.get(m.id)
            G.add_node(
                m.id,
                node_type="member",
                label=m.name,
                expertise_tags=m.expertise_tags or [],
                total_contributions=m.total_contributions or 0,
                declared_skills=(linked_user.skills if linked_user and linked_user.skills else []),
                role_title=(linked_user.role_title if linked_user else None),
            )

        # ---- Artifact nodes ----------------------------------------------
        for a in artifacts:
            G.add_node(
                f"artifact-{a.id}",
                node_type="artifact",
                label=a.title or a.id,
                artifact_type=a.source_type or "unknown",
                member_count=len(a.member_ids or []),
            )

        # ---- CONTRIBUTED_TO edges ----------------------------------------
        artifact_contributors: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for c in contribs:
            if c.artifact_id and c.artifact_id in artifact_map:
                weight = _temporal_decay(c.timestamp, now)
                artifact_contributors[c.artifact_id][c.member_id] += weight

        for art_id, member_weights in artifact_contributors.items():
            for mid, weight in member_weights.items():
                if mid in member_map:
                    G.add_edge(
                        mid,
                        f"artifact-{art_id}",
                        edge_type="CONTRIBUTED_TO",
                        weight=round(weight, 2),
                    )

        # ---- Topic nodes from contributions ------------------------------
        topic_member_weights: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        topic_artifact: dict[str, set[str]] = defaultdict(set)

        for c in contribs:
            decay = _temporal_decay(c.timestamp, now)
            type_weight = _contribution_type_weight(c.contribution_type)
            for topic in c.topics or []:
                topic_member_weights[topic][c.member_id] += decay * type_weight
                if c.artifact_id:
                    topic_artifact[topic].add(c.artifact_id)

        seen_topics: set[str] = set()
        for topic, mw in topic_member_weights.items():
            seen_topics.add(topic)
            tid = f"topic-{topic}"
            G.add_node(tid, node_type="topic", label=topic, member_count=len(mw))

            for mid, weight in mw.items():
                if mid in member_map:
                    G.add_edge(mid, tid, edge_type="KNOWS_ABOUT", weight=round(weight, 2))

            for art_id in topic_artifact.get(topic, set()):
                if art_id in artifact_map:
                    G.add_edge(
                        f"artifact-{art_id}",
                        tid,
                        edge_type="COVERS_TOPIC",
                        weight=1.0,
                    )

        # ---- Topics from expertise_tags ----------------------------------
        expertise_topic_members: dict[str, list[str]] = defaultdict(list)
        for m in members:
            for tag in self._normalize_tags(m.expertise_tags or []):
                if tag not in seen_topics:
                    expertise_topic_members[tag].append(m.id)

        for topic, member_ids in expertise_topic_members.items():
            seen_topics.add(topic)
            tid = f"topic-{topic}"
            G.add_node(tid, node_type="topic", label=topic, member_count=len(member_ids))
            for mid in member_ids:
                G.add_edge(mid, tid, edge_type="HAS_EXPERTISE", weight=1.0)

        # ---- User-declared skills as topic nodes -------------------------
        for mid, user in member_user_map.items():
            if not user.skills:
                continue
            for skill in user.skills:
                skill_lower = skill.strip().lower()
                if not skill_lower:
                    continue
                tid = f"topic-{skill_lower}"
                if tid not in G:
                    seen_topics.add(skill_lower)
                    G.add_node(tid, node_type="topic", label=skill_lower, member_count=1)
                else:
                    G.nodes[tid]["member_count"] = G.nodes[tid].get("member_count", 0) + 1

                if not G.has_edge(mid, tid):
                    G.add_edge(mid, tid, edge_type="DECLARED_SKILL", weight=0.8)

        # ---- Users with skills but NO linked member ----------------------
        for u in users:
            if u.linked_member_id or not u.skills:
                continue
            virtual_id = f"user-{u.id}"
            G.add_node(
                virtual_id,
                node_type="member",
                label=u.display_name or u.email,
                expertise_tags=[],
                total_contributions=0,
                declared_skills=u.skills,
                role_title=u.role_title,
                is_virtual=True,
            )
            for skill in u.skills:
                skill_lower = skill.strip().lower()
                if not skill_lower:
                    continue
                tid = f"topic-{skill_lower}"
                if tid not in G:
                    G.add_node(tid, node_type="topic", label=skill_lower, member_count=1)
                else:
                    G.nodes[tid]["member_count"] = G.nodes[tid].get("member_count", 0) + 1
                if not G.has_edge(virtual_id, tid):
                    G.add_edge(virtual_id, tid, edge_type="DECLARED_SKILL", weight=0.8)

        # ---- COLLABORATED_WITH edges -------------------------------------
        collab_pairs = self._get_collaboration_pairs()
        for (m1, m2), weight in collab_pairs.items():
            if m1 in G and m2 in G:
                G.add_edge(m1, m2, edge_type="COLLABORATED_WITH", weight=weight)

        # ---- Compute graph metrics ---------------------------------------
        self._compute_metrics(G)

        return G

    def _compute_metrics(self, G: nx.Graph):
        """Add PageRank, betweenness centrality, and community labels."""
        if G.number_of_nodes() == 0:
            return

        # PageRank
        try:
            pr = nx.pagerank(G, weight="weight", max_iter=100)
            for node_id, score in pr.items():
                G.nodes[node_id]["pagerank"] = round(score, 4)
        except Exception:
            logger.debug("PageRank computation failed, skipping")

        # Betweenness centrality
        try:
            bc = nx.betweenness_centrality(G, weight="weight", k=min(50, G.number_of_nodes()))
            for node_id, score in bc.items():
                G.nodes[node_id]["betweenness"] = round(score, 4)
        except Exception:
            logger.debug("Betweenness centrality computation failed, skipping")

        # Community detection via greedy modularity
        try:
            communities = nx.community.greedy_modularity_communities(G)
            for idx, community in enumerate(communities):
                for node_id in community:
                    G.nodes[node_id]["community"] = idx
        except Exception:
            logger.debug("Community detection failed, skipping")

    # ---- DB Query Helpers ------------------------------------------------

    def _query_members(self):
        if self.room_id:
            member_ids = [
                mid
                for (mid,) in self.db.query(ContributionRecord.member_id)
                .filter(ContributionRecord.room_id == self.room_id)
                .distinct()
                .all()
            ]
            return (self.db.query(MemberRecord).filter(MemberRecord.id.in_(member_ids)).all()) if member_ids else []
        return self.db.query(MemberRecord).all()

    def _query_artifacts(self):
        query = self.db.query(ArtifactRecord)
        if self.room_id:
            query = query.filter(ArtifactRecord.room_id == self.room_id)
        return query.all()

    def _query_contributions(self):
        query = self.db.query(ContributionRecord)
        if self.room_id:
            query = query.filter(ContributionRecord.room_id == self.room_id)
        return query.all()

    def _query_users(self) -> list:
        """Get all users with skills or linked members."""
        try:
            return self.db.query(UserRecord).all()
        except Exception:
            return []

    @staticmethod
    def _normalize_tags(tags: list[str]) -> list[str]:
        result = []
        for tag in tags:
            for part in tag.split(","):
                cleaned = part.strip().lower()
                if cleaned:
                    result.append(cleaned)
        return result

    def _get_topic_member_map(self) -> dict[str, dict[str, int]]:
        contribs = self._query_contributions()
        topic_members: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for c in contribs:
            for topic in c.topics or []:
                topic_members[topic][c.member_id] += 1
        return dict(topic_members)

    def _get_collaboration_pairs(self) -> dict[tuple[str, str], int]:
        artifacts = self._query_artifacts()
        pairs: dict[tuple[str, str], int] = defaultdict(int)
        for a in artifacts:
            member_ids = a.member_ids or []
            for i in range(len(member_ids)):
                for j in range(i + 1, len(member_ids)):
                    pair = tuple(sorted([member_ids[i], member_ids[j]]))
                    pairs[pair] += 1
        return pairs
