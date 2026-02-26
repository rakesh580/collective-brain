"""Three-layer knowledge graph: Social, Artifact, Concept.

Layers:
  Social   — Member nodes + COLLABORATED_WITH edges
  Artifact — ArtifactRecord nodes + CONTRIBUTED_TO edges (member → artifact)
  Concept  — Topic nodes + KNOWS_ABOUT / COVERS_TOPIC / HAS_EXPERTISE edges

Features:
  - Temporal decay on edges so recent contributions weigh more
  - Redis caching for expensive graph builds (optional)
  - "Stale expertise" pattern detection
"""

import math
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.member import MemberRecord
from app.models.artifact import ArtifactRecord
from app.models.contribution import ContributionRecord
from app.schemas.responses import GraphNode, GraphEdge

logger = logging.getLogger("collective_brain.graph")

# Half-life for temporal decay (days).  Contributions older than this
# contribute ~50 % of a recent one's weight.
_HALF_LIFE_DAYS = 180


def _temporal_decay(
    timestamp: datetime | None,
    now: datetime | None = None,
    half_life_days: float = _HALF_LIFE_DAYS,
) -> float:
    """Exponential decay weight: 1.0 for *now*, 0.5 at half-life, etc."""
    if timestamp is None:
        return 0.5  # unknown date → neutral weight
    now = now or datetime.utcnow()
    age_days = max(0, (now - timestamp).total_seconds() / 86400)
    return math.exp(-0.693 * age_days / half_life_days)  # ln(2) ≈ 0.693


class MemoryGraph:
    """Build and query a three-layer knowledge graph from the DB."""

    def __init__(self, db: Session, *, redis=None, room_id: str | None = None):
        self.db = db
        self._redis = redis  # optional RedisService for caching
        self.room_id = room_id

    def _query_members(self):
        """Get members, optionally filtered by room contributions."""
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
        """Get artifacts, optionally filtered by room."""
        query = self.db.query(ArtifactRecord)
        if self.room_id:
            query = query.filter(ArtifactRecord.room_id == self.room_id)
        return query.all()

    def _query_contributions(self):
        """Get contributions, optionally filtered by room."""
        query = self.db.query(ContributionRecord)
        if self.room_id:
            query = query.filter(ContributionRecord.room_id == self.room_id)
        return query.all()

    # ── Full Graph ────────────────────────────────────────────

    def build_full_graph(self) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Build Social + Artifact + Concept layers."""
        now = datetime.utcnow()
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        members = self._query_members()
        artifacts = self._query_artifacts()
        contribs = self._query_contributions()

        member_map = {m.id: m for m in members}
        artifact_map = {a.id: a for a in artifacts}

        # ── Social Layer: Member nodes ────────────────────────
        for m in members:
            nodes.append(
                GraphNode(
                    id=m.id,
                    type="member",
                    label=m.name,
                    properties={
                        "expertise_tags": m.expertise_tags or [],
                        "total_contributions": m.total_contributions or 0,
                    },
                    size=max(1.0, (m.total_contributions or 0) * 0.5),
                )
            )

        # ── Artifact Layer: Artifact nodes ────────────────────
        for a in artifacts:
            nodes.append(
                GraphNode(
                    id=f"artifact-{a.id}",
                    type="artifact",
                    label=a.title or a.id,
                    properties={
                        "artifact_type": a.source_type or "unknown",
                        "member_count": len(a.member_ids or []),
                    },
                    size=max(1.0, len(a.member_ids or []) * 1.5),
                )
            )

        # ── CONTRIBUTED_TO edges (member → artifact) ──────────
        # Build from ContributionRecords for temporal weighting
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
                    edges.append(
                        GraphEdge(
                            source=mid,
                            target=f"artifact-{art_id}",
                            type="CONTRIBUTED_TO",
                            weight=round(weight, 2),
                            label=f"weight {weight:.1f}",
                        )
                    )

        # ── Concept Layer: Topic nodes ────────────────────────
        # Aggregate topics from contributions with temporal decay
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
        for topic, member_weights in topic_member_weights.items():
            seen_topics.add(topic)
            nodes.append(
                GraphNode(
                    id=f"topic-{topic}",
                    type="topic",
                    label=topic,
                    properties={"member_count": len(member_weights)},
                    size=max(1.0, len(member_weights) * 2),
                )
            )
            # KNOWS_ABOUT edges (member → topic) with temporal weight
            for mid, weight in member_weights.items():
                if mid in member_map:
                    edges.append(
                        GraphEdge(
                            source=mid,
                            target=f"topic-{topic}",
                            type="KNOWS_ABOUT",
                            weight=round(weight, 2),
                            label=f"score {weight:.1f}",
                        )
                    )
            # COVERS_TOPIC edges (artifact → topic)
            for art_id in topic_artifact.get(topic, set()):
                if art_id in artifact_map:
                    edges.append(
                        GraphEdge(
                            source=f"artifact-{art_id}",
                            target=f"topic-{topic}",
                            type="COVERS_TOPIC",
                            weight=1.0,
                            label="covers",
                        )
                    )

        # Topics from expertise_tags that don't appear in contributions
        expertise_topic_members: dict[str, list[str]] = defaultdict(list)
        for m in members:
            for tag in self._normalize_tags(m.expertise_tags or []):
                if tag not in seen_topics:
                    expertise_topic_members[tag].append(m.id)

        for topic, member_ids in expertise_topic_members.items():
            seen_topics.add(topic)
            nodes.append(
                GraphNode(
                    id=f"topic-{topic}",
                    type="topic",
                    label=topic,
                    properties={"member_count": len(member_ids)},
                    size=max(1.0, len(member_ids) * 2),
                )
            )
            for mid in member_ids:
                edges.append(
                    GraphEdge(
                        source=mid,
                        target=f"topic-{topic}",
                        type="HAS_EXPERTISE",
                        weight=1,
                        label="expertise",
                    )
                )

        # ── COLLABORATED_WITH edges (member ↔ member) ─────────
        collab_pairs = self._get_collaboration_pairs()
        for (m1, m2), weight in collab_pairs.items():
            edges.append(
                GraphEdge(
                    source=m1,
                    target=m2,
                    type="COLLABORATED_WITH",
                    weight=weight,
                    label=f"{weight} shared artifacts",
                )
            )

        return nodes, edges

    # ── Expertise Matrix ──────────────────────────────────────

    def get_expertise_matrix(self) -> dict:
        """Return a member × topic matrix for heatmap visualization."""
        members = self._query_members()
        topic_members = self._get_topic_member_map()

        all_topics: set[str] = set(topic_members.keys())
        for m in members:
            for tag in self._normalize_tags(m.expertise_tags or []):
                all_topics.add(tag)

        sorted_topics = sorted(all_topics)
        member_data = []
        for m in members:
            scores: dict[str, float] = {}
            expertise_set = set(self._normalize_tags(m.expertise_tags or []))
            expertise_scores = self.compute_expertise_scores(m.id)

            for topic in sorted_topics:
                contrib_score = expertise_scores.get(topic, 0.0)
                has_tag = 1.0 if topic in expertise_set else 0.0
                scores[topic] = max(contrib_score, has_tag * 0.3)

            member_data.append({
                "id": m.id,
                "name": m.name,
                "scores": scores,
            })

        return {
            "members": member_data,
            "topics": sorted_topics,
        }

    # ── Sub-graphs ────────────────────────────────────────────

    def get_member_subgraph(
        self, member_id: str
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """1-hop neighbourhood around a member."""
        full_nodes, full_edges = self.build_full_graph()
        connected_ids = {member_id}
        relevant_edges = []
        for e in full_edges:
            if e.source == member_id or e.target == member_id:
                relevant_edges.append(e)
                connected_ids.add(e.source)
                connected_ids.add(e.target)

        relevant_nodes = [n for n in full_nodes if n.id in connected_ids]
        return relevant_nodes, relevant_edges

    def get_topic_subgraph(
        self, topic: str
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """2-hop neighbourhood: topic → members → their artifacts."""
        full_nodes, full_edges = self.build_full_graph()
        node_map = {n.id: n for n in full_nodes}

        topic_id = f"topic-{topic}"
        if topic_id not in node_map:
            return [], []

        # 1st hop: edges touching the topic
        hop1_ids = {topic_id}
        hop1_edges = []
        for e in full_edges:
            if e.source == topic_id or e.target == topic_id:
                hop1_edges.append(e)
                hop1_ids.add(e.source)
                hop1_ids.add(e.target)

        # 2nd hop: for each member found, include their artifact edges
        hop2_ids = set(hop1_ids)
        hop2_edges = list(hop1_edges)
        member_ids = {nid for nid in hop1_ids if nid in node_map and node_map[nid].type == "member"}
        for e in full_edges:
            if e in hop1_edges:
                continue
            if e.type == "CONTRIBUTED_TO" and e.source in member_ids:
                hop2_edges.append(e)
                hop2_ids.add(e.target)

        relevant_nodes = [n for n in full_nodes if n.id in hop2_ids]
        return relevant_nodes, hop2_edges

    # ── Expertise Scores ──────────────────────────────────────

    def compute_expertise_scores(self, member_id: str) -> dict[str, float]:
        """Compute temporally-weighted expertise score per topic."""
        now = datetime.utcnow()
        query = (
            self.db.query(ContributionRecord)
            .filter(ContributionRecord.member_id == member_id)
        )
        if self.room_id:
            query = query.filter(ContributionRecord.room_id == self.room_id)
        contribs = query.all()

        topic_scores: dict[str, float] = defaultdict(float)
        for c in contribs:
            decay = _temporal_decay(c.timestamp, now)
            type_w = _contribution_type_weight(c.contribution_type)
            for topic in c.topics or []:
                topic_scores[topic] += decay * type_w

        if topic_scores:
            max_score = max(topic_scores.values())
            if max_score > 0:
                topic_scores = {
                    k: round(v / max_score, 2) for k, v in topic_scores.items()
                }

        return dict(topic_scores)

    # ── Pattern Detection ─────────────────────────────────────

    def detect_patterns(self) -> list[dict]:
        """Identify collaboration patterns including stale expertise."""
        now = datetime.utcnow()
        patterns = []

        # Prefetch all members once to avoid N+1 queries
        members = self._query_members()
        member_map = {m.id: m for m in members}

        # Bus factor: topics with only 1 contributor
        topic_members = self._get_topic_member_map()
        for topic, member_counts in topic_members.items():
            if len(member_counts) == 1:
                member_id = list(member_counts.keys())[0]
                member = member_map.get(member_id)
                name = member.name if member else member_id
                patterns.append({
                    "type": "risk",
                    "title": f"Bus factor risk: {topic}",
                    "body": (
                        f"Only {name} has contributed to '{topic}'. "
                        "If they're unavailable, this area has no coverage."
                    ),
                    "related_members": [member_id],
                    "confidence": 0.8,
                })

        # Siloed members: no shared artifacts despite contributions
        collab_pairs = self._get_collaboration_pairs()
        for m in members:
            collab_count = sum(
                w for (m1, m2), w in collab_pairs.items() if m.id in (m1, m2)
            )
            if collab_count == 0 and (m.total_contributions or 0) > 2:
                patterns.append({
                    "type": "pattern",
                    "title": f"Siloed member: {m.name}",
                    "body": (
                        f"{m.name} has {int(m.total_contributions or 0)} "
                        "contributions but hasn't collaborated with others "
                        "on shared artifacts."
                    ),
                    "related_members": [m.id],
                    "confidence": 0.6,
                })

        # Strong collaboration pairs
        for (m1, m2), weight in collab_pairs.items():
            if weight >= 5:
                m1_rec = member_map.get(m1)
                m2_rec = member_map.get(m2)
                n1 = m1_rec.name if m1_rec else m1
                n2 = m2_rec.name if m2_rec else m2
                patterns.append({
                    "type": "pattern",
                    "title": f"Strong collaboration: {n1} & {n2}",
                    "body": (
                        f"{n1} and {n2} have collaborated on "
                        f"{weight} artifacts together."
                    ),
                    "related_members": [m1, m2],
                    "confidence": 0.7,
                })

        # Stale expertise: members inactive >90 days on a topic
        stale_threshold = now - timedelta(days=90)
        contribs = self._query_contributions()
        member_last_active: dict[str, datetime] = {}
        for c in contribs:
            if c.timestamp and c.member_id:
                prev = member_last_active.get(c.member_id)
                if prev is None or c.timestamp > prev:
                    member_last_active[c.member_id] = c.timestamp

        for m in members:
            last = member_last_active.get(m.id)
            if last and last < stale_threshold and (m.total_contributions or 0) > 3:
                days_ago = (now - last).days
                patterns.append({
                    "type": "risk",
                    "title": f"Stale expertise: {m.name}",
                    "body": (
                        f"{m.name} hasn't contributed in {days_ago} days. "
                        "Their knowledge may be outdated."
                    ),
                    "related_members": [m.id],
                    "confidence": 0.5,
                })

        return patterns

    # ── Helpers ────────────────────────────────────────────────

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
