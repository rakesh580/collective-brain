"""Graph querying: full graph retrieval, sub-graphs, expertise matrix/scores."""

import networkx as nx

from app.schemas.responses import GraphEdge, GraphNode


class GraphQueryMixin:
    """Mixin providing graph query and sub-graph extraction methods.

    Expects the host class to provide ``_get_or_build_nx_graph()``,
    ``_compute_node_size()``, and ``_edge_label()``.
    """

    # ---- Public API: Full Graph ------------------------------------------

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
            if ntype == "member":
                return max(2.0, pr * 500)
            elif ntype == "topic":
                return max(1.0, pr * 400)
            else:
                return max(1.0, pr * 300)

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

    # ---- Expertise Matrix ------------------------------------------------

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

    # ---- Sub-graphs ------------------------------------------------------

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
        """2-hop neighbourhood: topic -> members -> their artifacts."""
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

    # ---- Expertise Scores ------------------------------------------------

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
