"""Three-layer knowledge graph: Social, Artifact, Concept.

Layers:
  Social   — Member nodes + COLLABORATED_WITH edges
  Artifact — ArtifactRecord nodes + CONTRIBUTED_TO edges (member → artifact)
  Concept  — Topic nodes + KNOWS_ABOUT / COVERS_TOPIC / HAS_EXPERTISE / DECLARED_SKILL edges

Features:
  - NetworkX in-memory graph with cache invalidation
  - Temporal decay on edges so recent contributions weigh more
  - User-declared skills integrated as topic nodes
  - PageRank, betweenness centrality, community detection
"""

import asyncio
import math
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import networkx as nx
from sqlalchemy.orm import Session

from app.models.member import MemberRecord
from app.models.artifact import ArtifactRecord
from app.models.contribution import ContributionRecord
from app.models.user import UserRecord
from app.schemas.responses import GraphNode, GraphEdge

logger = logging.getLogger("collective_brain.graph")

# Half-life for temporal decay (days).
_HALF_LIFE_DAYS = 180

# Global cached graph — dict operations are atomic under CPython's GIL
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

    Safe to call from both sync and async contexts — dict operations
    on CPython are atomic under the GIL.
    """
    if room_id in _graph_cache:
        _graph_cache.pop(room_id, None)
    # Also invalidate the global (None) cache
    if room_id is not None:
        _graph_cache.pop(None, None)


def _temporal_decay(
    timestamp: datetime | None,
    now: datetime | None = None,
    half_life_days: float = _HALF_LIFE_DAYS,
) -> float:
    """Exponential decay weight: 1.0 for *now*, 0.5 at half-life, etc."""
    if timestamp is None:
        return 0.5
    now = now or datetime.now(timezone.utc)
    age_days = max(0, (now - timestamp).total_seconds() / 86400)
    return math.exp(-0.693 * age_days / half_life_days)


def _contribution_type_weight(ctype: str | None) -> float:
    """Assign weight by contribution type — code weighs more than chat."""
    weights = {
        "git_content": 0.5,
        "slack_content": 0.3,
        "discord_content": 0.3,
        "markdown_content": 0.25,
        "tasks_content": 0.15,
        "document_content": 0.35,
    }
    return weights.get(ctype or "", 0.2)


class MemoryGraph:
    """Build and query a three-layer knowledge graph backed by NetworkX."""

    def __init__(self, db: Session, *, redis=None, room_id: str | None = None):
        self.db = db
        self._redis = redis
        self.room_id = room_id

    # ── NetworkX Graph Building ────────────────────────────────

    def _get_or_build_nx_graph(self) -> nx.Graph:
        """Return cached NetworkX graph or build a fresh one.

        Uses dict operations that are atomic under CPython's GIL.
        """
        cached = _graph_cache.get(self.room_id)
        if cached and not cached.is_stale:
            return cached.G

        # Build graph (may take time for large datasets)
        G = self._build_nx_graph()
        _graph_cache[self.room_id] = CachedGraph(G, time.time())
        return G

    def _build_nx_graph(self) -> nx.Graph:
        """Build a full NetworkX graph from DB data."""
        now = datetime.now(timezone.utc)
        G = nx.Graph()

        members = self._query_members()
        artifacts = self._query_artifacts()
        contribs = self._query_contributions()
        users = self._query_users()

        member_map = {m.id: m for m in members}
        artifact_map = {a.id: a for a in artifacts}

        # Map member → linked user for skill integration
        member_user_map: dict[str, UserRecord] = {}
        for u in users:
            if u.linked_member_id and u.linked_member_id in member_map:
                member_user_map[u.linked_member_id] = u

        # ── Member nodes ──────────────────────────────────────
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

        # ── Artifact nodes ────────────────────────────────────
        for a in artifacts:
            G.add_node(
                f"artifact-{a.id}",
                node_type="artifact",
                label=a.title or a.id,
                artifact_type=a.source_type or "unknown",
                member_count=len(a.member_ids or []),
            )

        # ── CONTRIBUTED_TO edges ──────────────────────────────
        artifact_contributors: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
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

        # ── Topic nodes from contributions ────────────────────
        topic_member_weights: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
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
                        f"artifact-{art_id}", tid,
                        edge_type="COVERS_TOPIC", weight=1.0,
                    )

        # ── Topics from expertise_tags ────────────────────────
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

        # ── User-declared skills as topic nodes ───────────────
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
                    # Increment member count
                    G.nodes[tid]["member_count"] = G.nodes[tid].get("member_count", 0) + 1

                # Add DECLARED_SKILL edge if not already connected
                if not G.has_edge(mid, tid):
                    G.add_edge(mid, tid, edge_type="DECLARED_SKILL", weight=0.8)

        # ── Users with skills but NO linked member ────────────
        # Create virtual member nodes so their skills still appear
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

        # ── COLLABORATED_WITH edges ───────────────────────────
        collab_pairs = self._get_collaboration_pairs()
        for (m1, m2), weight in collab_pairs.items():
            if m1 in G and m2 in G:
                G.add_edge(m1, m2, edge_type="COLLABORATED_WITH", weight=weight)

        # ── Compute graph metrics ─────────────────────────────
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

        # Betweenness centrality (only for member/topic nodes for performance)
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

    # ── Public API: Full Graph ─────────────────────────────────

    def build_full_graph(self) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Build Social + Artifact + Concept layers from cached NetworkX graph."""
        G = self._get_or_build_nx_graph()
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        for node_id, data in G.nodes(data=True):
            ntype = data.get("node_type", "unknown")
            props: dict = {}

            if ntype == "member":
                props["expertise_tags"] = data.get("expertise_tags", [])
                props["total_contributions"] = data.get("total_contributions", 0)
                declared = data.get("declared_skills", [])
                if declared:
                    props["declared_skills"] = declared
                rt = data.get("role_title")
                if rt:
                    props["role_title"] = rt
            elif ntype == "artifact":
                props["artifact_type"] = data.get("artifact_type", "unknown")
                props["member_count"] = data.get("member_count", 0)
            elif ntype == "topic":
                props["member_count"] = data.get("member_count", 0)

            # Add graph metrics
            if "pagerank" in data:
                props["pagerank"] = data["pagerank"]
            if "betweenness" in data:
                props["betweenness"] = data["betweenness"]
            if "community" in data:
                props["community"] = data["community"]

            size = self._compute_node_size(ntype, data)
            nodes.append(
                GraphNode(
                    id=node_id,
                    type=ntype,
                    label=data.get("label", node_id),
                    properties=props,
                    size=size,
                )
            )

        for u, v, data in G.edges(data=True):
            etype = data.get("edge_type", "UNKNOWN")
            weight = data.get("weight", 1.0)
            label = self._edge_label(etype, weight)
            edges.append(
                GraphEdge(
                    source=u, target=v, type=etype,
                    weight=weight, label=label,
                )
            )

        return nodes, edges

    def _compute_node_size(self, ntype: str, data: dict) -> float:
        """Size nodes using PageRank when available, fallback to simple heuristics."""
        pr = data.get("pagerank", 0)
        if pr > 0:
            # Scale PageRank to a visible size range
            if ntype == "member":
                return max(2.0, pr * 500)
            elif ntype == "topic":
                return max(1.0, pr * 400)
            else:
                return max(1.0, pr * 300)

        # Fallback
        if ntype == "member":
            return max(1.0, (data.get("total_contributions", 0)) * 0.5)
        elif ntype == "topic":
            return max(1.0, data.get("member_count", 0) * 2)
        else:
            return max(1.0, data.get("member_count", 0) * 1.5)

    @staticmethod
    def _edge_label(etype: str, weight: float) -> str:
        if etype == "CONTRIBUTED_TO":
            return f"weight {weight:.1f}"
        elif etype == "KNOWS_ABOUT":
            return f"score {weight:.1f}"
        elif etype == "COLLABORATED_WITH":
            return f"{int(weight)} shared artifacts"
        elif etype == "HAS_EXPERTISE":
            return "expertise"
        elif etype == "DECLARED_SKILL":
            return "declared"
        elif etype == "COVERS_TOPIC":
            return "covers"
        return ""

    # ── Expertise Matrix ───────────────────────────────────────

    def get_expertise_matrix(self) -> dict:
        """Return a member x topic matrix for heatmap visualization."""
        G = self._get_or_build_nx_graph()

        member_nodes = [
            (nid, d) for nid, d in G.nodes(data=True) if d.get("node_type") == "member"
        ]
        topic_nodes = [
            (nid, d) for nid, d in G.nodes(data=True) if d.get("node_type") == "topic"
        ]

        all_topics = sorted(d["label"] for _, d in topic_nodes)
        topic_id_map = {d["label"]: nid for nid, d in topic_nodes}

        member_data = []
        for mid, mdata in member_nodes:
            scores: dict[str, float] = {}
            for topic_label in all_topics:
                tid = topic_id_map.get(topic_label)
                if tid and G.has_edge(mid, tid):
                    edge_data = G.edges[mid, tid]
                    etype = edge_data.get("edge_type", "")
                    w = edge_data.get("weight", 0)
                    if etype == "DECLARED_SKILL":
                        scores[topic_label] = max(w, 0.3)
                    else:
                        scores[topic_label] = w
                else:
                    scores[topic_label] = 0.0
            member_data.append({
                "id": mid,
                "name": mdata.get("label", mid),
                "scores": scores,
            })

        # Normalize scores per topic
        if member_data and all_topics:
            for topic in all_topics:
                max_score = max((m["scores"].get(topic, 0) for m in member_data), default=0)
                if max_score > 0:
                    for m in member_data:
                        m["scores"][topic] = round(m["scores"].get(topic, 0) / max_score, 2)

        return {"members": member_data, "topics": all_topics}

    # ── Sub-graphs ─────────────────────────────────────────────

    def get_member_subgraph(
        self, member_id: str
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """1-hop neighbourhood around a member."""
        G = self._get_or_build_nx_graph()
        if member_id not in G:
            return [], []

        neighbors = set(G.neighbors(member_id))
        neighbors.add(member_id)

        sub = G.subgraph(neighbors)
        return self._nx_to_response(sub)

    def get_topic_subgraph(
        self, topic: str
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """2-hop neighbourhood: topic → members → their artifacts."""
        G = self._get_or_build_nx_graph()
        topic_id = f"topic-{topic}"
        if topic_id not in G:
            return [], []

        # 1st hop
        hop1 = set(G.neighbors(topic_id))
        hop1.add(topic_id)

        # 2nd hop: for members found, include their artifact edges
        hop2 = set(hop1)
        for nid in hop1:
            if G.nodes[nid].get("node_type") == "member":
                for nbr in G.neighbors(nid):
                    if G.nodes[nbr].get("node_type") == "artifact":
                        hop2.add(nbr)

        sub = G.subgraph(hop2)
        return self._nx_to_response(sub)

    def _nx_to_response(
        self, G: nx.Graph
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Convert a NetworkX (sub)graph to response format."""
        nodes = []
        edges = []
        for nid, data in G.nodes(data=True):
            ntype = data.get("node_type", "unknown")
            props: dict = {}
            if ntype == "member":
                props["expertise_tags"] = data.get("expertise_tags", [])
                props["total_contributions"] = data.get("total_contributions", 0)
                declared = data.get("declared_skills", [])
                if declared:
                    props["declared_skills"] = declared
            elif ntype == "artifact":
                props["artifact_type"] = data.get("artifact_type", "unknown")
                props["member_count"] = data.get("member_count", 0)
            elif ntype == "topic":
                props["member_count"] = data.get("member_count", 0)

            if "pagerank" in data:
                props["pagerank"] = data["pagerank"]
            if "community" in data:
                props["community"] = data["community"]

            size = self._compute_node_size(ntype, data)
            nodes.append(GraphNode(
                id=nid, type=ntype, label=data.get("label", nid),
                properties=props, size=size,
            ))

        for u, v, data in G.edges(data=True):
            etype = data.get("edge_type", "UNKNOWN")
            weight = data.get("weight", 1.0)
            edges.append(GraphEdge(
                source=u, target=v, type=etype,
                weight=weight, label=self._edge_label(etype, weight),
            ))

        return nodes, edges

    # ── Expertise Scores ───────────────────────────────────────

    def compute_expertise_scores(self, member_id: str) -> dict[str, float]:
        """Compute temporally-weighted expertise score per topic."""
        G = self._get_or_build_nx_graph()
        if member_id not in G:
            return {}

        topic_scores: dict[str, float] = {}
        for nbr in G.neighbors(member_id):
            if G.nodes[nbr].get("node_type") == "topic":
                edge_data = G.edges[member_id, nbr]
                weight = edge_data.get("weight", 0)
                topic_label = G.nodes[nbr].get("label", nbr)
                topic_scores[topic_label] = weight

        if topic_scores:
            max_score = max(topic_scores.values())
            if max_score > 0:
                topic_scores = {
                    k: round(v / max_score, 2) for k, v in topic_scores.items()
                }

        return topic_scores

    # ── Pattern Detection ──────────────────────────────────────

    def detect_patterns(self) -> list[dict]:
        """Identify collaboration patterns using graph algorithms."""
        G = self._get_or_build_nx_graph()
        patterns = []

        member_nodes = {
            nid: d for nid, d in G.nodes(data=True) if d.get("node_type") == "member"
        }

        # Bus factor: topics with only 1 member contributor
        topic_nodes = {
            nid: d for nid, d in G.nodes(data=True) if d.get("node_type") == "topic"
        }
        for tid, tdata in topic_nodes.items():
            member_neighbors = [
                n for n in G.neighbors(tid) if G.nodes[n].get("node_type") == "member"
            ]
            if len(member_neighbors) == 1:
                mid = member_neighbors[0]
                name = G.nodes[mid].get("label", mid)
                topic = tdata.get("label", tid)
                patterns.append({
                    "type": "risk",
                    "title": f"Bus factor risk: {topic}",
                    "body": (
                        f"Only {name} has contributed to '{topic}'. "
                        "If they're unavailable, this area has no coverage."
                    ),
                    "related_members": [mid],
                    "confidence": 0.8,
                })

        # Siloed members: no collaboration edges
        for mid, mdata in member_nodes.items():
            total = mdata.get("total_contributions", 0)
            has_collab = any(
                G.edges[mid, nbr].get("edge_type") == "COLLABORATED_WITH"
                for nbr in G.neighbors(mid)
                if G.has_edge(mid, nbr)
            )
            if not has_collab and total > 2:
                patterns.append({
                    "type": "pattern",
                    "title": f"Siloed member: {mdata.get('label', mid)}",
                    "body": (
                        f"{mdata.get('label', mid)} has {int(total)} "
                        "contributions but hasn't collaborated with others."
                    ),
                    "related_members": [mid],
                    "confidence": 0.6,
                })

        # Strong collaboration pairs
        for u, v, edata in G.edges(data=True):
            if edata.get("edge_type") == "COLLABORATED_WITH" and edata.get("weight", 0) >= 5:
                n1 = G.nodes[u].get("label", u)
                n2 = G.nodes[v].get("label", v)
                w = edata["weight"]
                patterns.append({
                    "type": "pattern",
                    "title": f"Strong collaboration: {n1} & {n2}",
                    "body": f"{n1} and {n2} have collaborated on {int(w)} artifacts together.",
                    "related_members": [u, v],
                    "confidence": 0.7,
                })

        # Key connector nodes (high betweenness centrality)
        for mid, mdata in member_nodes.items():
            bc = mdata.get("betweenness", 0)
            if bc > 0.1:
                patterns.append({
                    "type": "pattern",
                    "title": f"Key connector: {mdata.get('label', mid)}",
                    "body": (
                        f"{mdata.get('label', mid)} is a key connector in the knowledge network "
                        f"(betweenness centrality: {bc:.2f}). They bridge different knowledge areas."
                    ),
                    "related_members": [mid],
                    "confidence": 0.7,
                })

        # Stale expertise: members inactive >90 days
        now = datetime.now(timezone.utc)
        stale_threshold = now - timedelta(days=90)
        contribs = self._query_contributions()
        member_last_active: dict[str, datetime] = {}
        for c in contribs:
            if c.timestamp and c.member_id:
                prev = member_last_active.get(c.member_id)
                if prev is None or c.timestamp > prev:
                    member_last_active[c.member_id] = c.timestamp

        for mid, mdata in member_nodes.items():
            last = member_last_active.get(mid)
            total = mdata.get("total_contributions", 0)
            if last and last < stale_threshold and total > 3:
                days_ago = (now - last).days
                patterns.append({
                    "type": "risk",
                    "title": f"Stale expertise: {mdata.get('label', mid)}",
                    "body": (
                        f"{mdata.get('label', mid)} hasn't contributed in {days_ago} days. "
                        "Their knowledge may be outdated."
                    ),
                    "related_members": [mid],
                    "confidence": 0.5,
                })

        return patterns

    # ── Graph Analytics (new) ──────────────────────────────────

    def get_graph_stats(self) -> dict:
        """Return high-level graph statistics."""
        G = self._get_or_build_nx_graph()
        member_count = sum(1 for _, d in G.nodes(data=True) if d.get("node_type") == "member")
        topic_count = sum(1 for _, d in G.nodes(data=True) if d.get("node_type") == "topic")
        artifact_count = sum(1 for _, d in G.nodes(data=True) if d.get("node_type") == "artifact")

        # Count communities
        communities = set()
        for _, d in G.nodes(data=True):
            if "community" in d:
                communities.add(d["community"])

        # Top PageRank members
        member_pr = sorted(
            [(nid, d) for nid, d in G.nodes(data=True) if d.get("node_type") == "member"],
            key=lambda x: x[1].get("pagerank", 0),
            reverse=True,
        )[:5]

        return {
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "members": member_count,
            "topics": topic_count,
            "artifacts": artifact_count,
            "communities": len(communities),
            "density": round(nx.density(G), 4) if G.number_of_nodes() > 1 else 0,
            "top_members": [
                {"id": nid, "name": d.get("label", nid), "pagerank": d.get("pagerank", 0)}
                for nid, d in member_pr
            ],
        }

    # ── DB Query Helpers ───────────────────────────────────────

    def _query_members(self):
        if self.room_id:
            member_ids = [
                mid for (mid,) in
                self.db.query(ContributionRecord.member_id)
                .filter(ContributionRecord.room_id == self.room_id)
                .distinct()
                .all()
            ]
            return (
                self.db.query(MemberRecord)
                .filter(MemberRecord.id.in_(member_ids))
                .all()
            ) if member_ids else []
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

    # ── Cluster Details ──────────────────────────────────────────

    def get_cluster_details(self) -> dict:
        """Return detailed information about each community/cluster."""
        G = self._get_or_build_nx_graph()

        # Group nodes by community
        clusters: dict[int, dict] = {}
        for nid, data in G.nodes(data=True):
            community = data.get("community")
            if community is None:
                continue
            if community not in clusters:
                clusters[community] = {
                    "id": community,
                    "members": [],
                    "topics": [],
                    "artifacts": [],
                    "total_contributions": 0,
                }
            ntype = data.get("node_type", "")
            if ntype == "member":
                clusters[community]["members"].append({
                    "id": nid,
                    "name": data.get("label", nid),
                    "pagerank": data.get("pagerank", 0),
                    "contributions": data.get("total_contributions", 0),
                })
                clusters[community]["total_contributions"] += data.get("total_contributions", 0)
            elif ntype == "topic":
                clusters[community]["topics"].append(data.get("label", nid))
            elif ntype == "artifact":
                clusters[community]["artifacts"].append(data.get("label", nid))

        # Sort clusters by total contributions
        sorted_clusters = sorted(clusters.values(), key=lambda c: c["total_contributions"], reverse=True)

        # Add inter-cluster edges count
        for cluster in sorted_clusters:
            member_ids = {m["id"] for m in cluster["members"]}
            internal_edges = 0
            external_edges = 0
            for mid in member_ids:
                for nbr in G.neighbors(mid):
                    nbr_community = G.nodes[nbr].get("community")
                    if nbr_community == cluster["id"]:
                        internal_edges += 1
                    else:
                        external_edges += 1
            cluster["internal_edges"] = internal_edges // 2
            cluster["external_edges"] = external_edges
            cluster["cohesion"] = round(
                internal_edges / max(1, internal_edges + external_edges), 2
            )

        return {"clusters": sorted_clusters, "total_clusters": len(sorted_clusters)}

    # ── Expertise Gap Analysis ────────────────────────────────────

    def get_expertise_gaps(self) -> dict:
        """Identify topics with bus factor risks and expertise gaps."""
        G = self._get_or_build_nx_graph()

        topic_nodes = {
            nid: d for nid, d in G.nodes(data=True)
            if d.get("node_type") == "topic"
        }
        member_nodes = {
            nid: d for nid, d in G.nodes(data=True)
            if d.get("node_type") == "member"
        }

        bus_factor_risks = []
        well_covered = []
        uncovered = []

        for tid, tdata in topic_nodes.items():
            member_experts = []
            for nbr in G.neighbors(tid):
                if G.nodes[nbr].get("node_type") == "member":
                    edge = G.edges[nbr, tid]
                    member_experts.append({
                        "id": nbr,
                        "name": G.nodes[nbr].get("label", nbr),
                        "weight": edge.get("weight", 0),
                        "edge_type": edge.get("edge_type", ""),
                    })

            topic_label = tdata.get("label", tid)

            if len(member_experts) == 0:
                uncovered.append({"topic": topic_label, "experts": []})
            elif len(member_experts) == 1:
                bus_factor_risks.append({
                    "topic": topic_label,
                    "sole_expert": member_experts[0],
                    "severity": "high",
                })
            elif len(member_experts) == 2:
                bus_factor_risks.append({
                    "topic": topic_label,
                    "experts": member_experts,
                    "severity": "medium",
                })
            else:
                well_covered.append({
                    "topic": topic_label,
                    "expert_count": len(member_experts),
                    "top_expert": max(member_experts, key=lambda e: e["weight"]),
                })

        # Member breadth analysis
        member_breadth = []
        for mid, mdata in member_nodes.items():
            topic_count = sum(
                1 for nbr in G.neighbors(mid)
                if G.nodes[nbr].get("node_type") == "topic"
            )
            member_breadth.append({
                "id": mid,
                "name": mdata.get("label", mid),
                "topic_count": topic_count,
                "contributions": mdata.get("total_contributions", 0),
            })

        member_breadth.sort(key=lambda m: m["topic_count"], reverse=True)

        return {
            "bus_factor_risks": bus_factor_risks,
            "well_covered": well_covered,
            "uncovered": uncovered,
            "member_breadth": member_breadth[:10],
            "summary": {
                "total_topics": len(topic_nodes),
                "at_risk": len(bus_factor_risks),
                "well_covered": len(well_covered),
                "uncovered": len(uncovered),
                "coverage_pct": round(
                    len(well_covered) / max(1, len(topic_nodes)) * 100, 1
                ),
            },
        }

    # ── Expert Routing ──────────────────────────────────────────

    def find_experts_for_topics(
        self, topics: list[str], top_k: int = 3
    ) -> list[dict]:
        """Find the best experts for a set of query topics.

        Scoring formula per member:
            final = expertise_score * 0.6 + pagerank * 0.2 + recency * 0.2

        Returns a sorted list (highest score first) of dicts with keys:
            member_id, name, match_score, expertise_topics, last_active,
            availability_hint
        """
        G = self._get_or_build_nx_graph()

        # Normalise query topics for matching
        query_topics = {t.strip().lower() for t in topics if t.strip()}
        if not query_topics:
            return []

        # Collect all member nodes
        member_nodes = {
            nid: d
            for nid, d in G.nodes(data=True)
            if d.get("node_type") == "member"
        }

        if not member_nodes:
            return []

        # Determine global max PageRank among members for normalisation
        max_pr = max(
            (d.get("pagerank", 0) for d in member_nodes.values()), default=0
        ) or 1.0

        # Build per-member last-active map from contributions
        contribs = self._query_contributions()
        member_last_active: dict[str, datetime] = {}
        for c in contribs:
            if c.timestamp and c.member_id:
                prev = member_last_active.get(c.member_id)
                if prev is None or c.timestamp > prev:
                    member_last_active[c.member_id] = c.timestamp

        now = datetime.now(timezone.utc)
        scored: list[dict] = []

        for mid, mdata in member_nodes.items():
            # Compute expertise scores for this member
            expertise = self.compute_expertise_scores(mid)
            if not expertise:
                continue

            # Find matching topics
            matched_topics: list[str] = []
            expertise_score = 0.0
            for qt in query_topics:
                for topic_label, score in expertise.items():
                    if qt in topic_label.lower() or topic_label.lower() in qt:
                        matched_topics.append(topic_label)
                        expertise_score += score
                        break  # one match per query topic

            if not matched_topics:
                continue

            # Normalise expertise_score to [0, 1]
            expertise_score = min(expertise_score / max(len(query_topics), 1), 1.0)

            # PageRank component (normalised)
            pr = mdata.get("pagerank", 0)
            pr_norm = pr / max_pr if max_pr > 0 else 0

            # Recency component
            last_active = member_last_active.get(mid)
            recency = _temporal_decay(last_active, now, half_life_days=90)

            # Weighted final score
            match_score = round(
                expertise_score * 0.6 + pr_norm * 0.2 + recency * 0.2,
                4,
            )

            # Availability hint based on recency
            if last_active:
                days_ago = (now - last_active).days
                if days_ago <= 7:
                    availability_hint = "active"
                elif days_ago <= 30:
                    availability_hint = "recently active"
                elif days_ago <= 90:
                    availability_hint = "occasionally active"
                else:
                    availability_hint = "inactive"
            else:
                availability_hint = "unknown"

            scored.append({
                "member_id": mid,
                "name": mdata.get("label", mid),
                "match_score": match_score,
                "expertise_topics": list(set(matched_topics)),
                "last_active": last_active,
                "availability_hint": availability_hint,
            })

        # Sort descending by match_score
        scored.sort(key=lambda x: x["match_score"], reverse=True)
        return scored[:top_k]

    def _get_topic_member_map(self) -> dict[str, dict[str, int]]:
        contribs = self._query_contributions()
        topic_members: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
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
