"""Graph analysis: pattern detection, stats, clusters, expertise gaps, expert routing."""

from datetime import UTC, datetime, timedelta

import networkx as nx

from .builder import _temporal_decay


class GraphAnalysisMixin:
    """Mixin providing analytical methods over the knowledge graph.

    Expects the host class to provide ``_get_or_build_nx_graph()``,
    ``_query_contributions()``, and ``compute_expertise_scores()``.
    """

    # ---- Pattern Detection -----------------------------------------------

    def detect_patterns(self) -> list[dict]:
        """Identify collaboration patterns using graph algorithms."""
        G = self._get_or_build_nx_graph()
        patterns = []

        member_nodes = {nid: d for nid, d in G.nodes(data=True) if d.get("node_type") == "member"}

        # Bus factor: topics with only 1 member contributor
        topic_nodes = {nid: d for nid, d in G.nodes(data=True) if d.get("node_type") == "topic"}
        for tid, tdata in topic_nodes.items():
            member_neighbors = [n for n in G.neighbors(tid) if G.nodes[n].get("node_type") == "member"]
            if len(member_neighbors) == 1:
                mid = member_neighbors[0]
                name = G.nodes[mid].get("label", mid)
                topic = tdata.get("label", tid)
                patterns.append(
                    {
                        "type": "risk",
                        "title": f"Bus factor risk: {topic}",
                        "body": (
                            f"Only {name} has contributed to '{topic}'. "
                            "If they're unavailable, this area has no coverage."
                        ),
                        "related_members": [mid],
                        "confidence": 0.8,
                    }
                )

        # Siloed members: no collaboration edges
        for mid, mdata in member_nodes.items():
            total = mdata.get("total_contributions", 0)
            has_collab = any(
                G.edges[mid, nbr].get("edge_type") == "COLLABORATED_WITH"
                for nbr in G.neighbors(mid)
                if G.has_edge(mid, nbr)
            )
            if not has_collab and total > 2:
                patterns.append(
                    {
                        "type": "pattern",
                        "title": f"Siloed member: {mdata.get('label', mid)}",
                        "body": (
                            f"{mdata.get('label', mid)} has {int(total)} "
                            "contributions but hasn't collaborated with others."
                        ),
                        "related_members": [mid],
                        "confidence": 0.6,
                    }
                )

        # Strong collaboration pairs
        for u, v, edata in G.edges(data=True):
            if edata.get("edge_type") == "COLLABORATED_WITH" and edata.get("weight", 0) >= 5:
                n1 = G.nodes[u].get("label", u)
                n2 = G.nodes[v].get("label", v)
                w = edata["weight"]
                patterns.append(
                    {
                        "type": "pattern",
                        "title": f"Strong collaboration: {n1} & {n2}",
                        "body": f"{n1} and {n2} have collaborated on {int(w)} artifacts together.",
                        "related_members": [u, v],
                        "confidence": 0.7,
                    }
                )

        # Key connector nodes (high betweenness centrality)
        for mid, mdata in member_nodes.items():
            bc = mdata.get("betweenness", 0)
            if bc > 0.1:
                patterns.append(
                    {
                        "type": "pattern",
                        "title": f"Key connector: {mdata.get('label', mid)}",
                        "body": (
                            f"{mdata.get('label', mid)} is a key connector in the knowledge network "
                            f"(betweenness centrality: {bc:.2f}). They bridge different knowledge areas."
                        ),
                        "related_members": [mid],
                        "confidence": 0.7,
                    }
                )

        # Stale expertise: members inactive >90 days
        now = datetime.now(UTC)
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
                patterns.append(
                    {
                        "type": "risk",
                        "title": f"Stale expertise: {mdata.get('label', mid)}",
                        "body": (
                            f"{mdata.get('label', mid)} hasn't contributed in {days_ago} days. "
                            "Their knowledge may be outdated."
                        ),
                        "related_members": [mid],
                        "confidence": 0.5,
                    }
                )

        return patterns

    # ---- Graph Analytics -------------------------------------------------

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
                {"id": nid, "name": d.get("label", nid), "pagerank": d.get("pagerank", 0)} for nid, d in member_pr
            ],
        }

    # ---- Cluster Details -------------------------------------------------

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
                clusters[community]["members"].append(
                    {
                        "id": nid,
                        "name": data.get("label", nid),
                        "pagerank": data.get("pagerank", 0),
                        "contributions": data.get("total_contributions", 0),
                    }
                )
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
            cluster["cohesion"] = round(internal_edges / max(1, internal_edges + external_edges), 2)

        return {"clusters": sorted_clusters, "total_clusters": len(sorted_clusters)}

    # ---- Expertise Gap Analysis ------------------------------------------

    def get_expertise_gaps(self) -> dict:
        """Identify topics with bus factor risks and expertise gaps."""
        G = self._get_or_build_nx_graph()

        topic_nodes = {nid: d for nid, d in G.nodes(data=True) if d.get("node_type") == "topic"}
        member_nodes = {nid: d for nid, d in G.nodes(data=True) if d.get("node_type") == "member"}

        bus_factor_risks = []
        well_covered = []
        uncovered = []

        for tid, tdata in topic_nodes.items():
            member_experts = []
            for nbr in G.neighbors(tid):
                if G.nodes[nbr].get("node_type") == "member":
                    edge = G.edges[nbr, tid]
                    member_experts.append(
                        {
                            "id": nbr,
                            "name": G.nodes[nbr].get("label", nbr),
                            "weight": edge.get("weight", 0),
                            "edge_type": edge.get("edge_type", ""),
                        }
                    )

            topic_label = tdata.get("label", tid)

            if len(member_experts) == 0:
                uncovered.append({"topic": topic_label, "experts": []})
            elif len(member_experts) == 1:
                bus_factor_risks.append(
                    {
                        "topic": topic_label,
                        "sole_expert": member_experts[0],
                        "severity": "high",
                    }
                )
            elif len(member_experts) == 2:
                bus_factor_risks.append(
                    {
                        "topic": topic_label,
                        "experts": member_experts,
                        "severity": "medium",
                    }
                )
            else:
                well_covered.append(
                    {
                        "topic": topic_label,
                        "expert_count": len(member_experts),
                        "top_expert": max(member_experts, key=lambda e: e["weight"]),
                    }
                )

        # Member breadth analysis
        member_breadth = []
        for mid, mdata in member_nodes.items():
            topic_count = sum(1 for nbr in G.neighbors(mid) if G.nodes[nbr].get("node_type") == "topic")
            member_breadth.append(
                {
                    "id": mid,
                    "name": mdata.get("label", mid),
                    "topic_count": topic_count,
                    "contributions": mdata.get("total_contributions", 0),
                }
            )

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
                "coverage_pct": round(len(well_covered) / max(1, len(topic_nodes)) * 100, 1),
            },
        }

    # ---- Expert Routing --------------------------------------------------

    def find_experts_for_topics(self, topics: list[str], top_k: int = 3) -> list[dict]:
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
        member_nodes = {nid: d for nid, d in G.nodes(data=True) if d.get("node_type") == "member"}

        if not member_nodes:
            return []

        # Determine global max PageRank among members for normalisation
        max_pr = max((d.get("pagerank", 0) for d in member_nodes.values()), default=0) or 1.0

        # Build per-member last-active map from contributions
        contribs = self._query_contributions()
        member_last_active: dict[str, datetime] = {}
        for c in contribs:
            if c.timestamp and c.member_id:
                prev = member_last_active.get(c.member_id)
                if prev is None or c.timestamp > prev:
                    member_last_active[c.member_id] = c.timestamp

        now = datetime.now(UTC)
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

            scored.append(
                {
                    "member_id": mid,
                    "name": mdata.get("label", mid),
                    "match_score": match_score,
                    "expertise_topics": list(set(matched_topics)),
                    "last_active": last_active,
                    "availability_hint": availability_hint,
                }
            )

        # Sort descending by match_score
        scored.sort(key=lambda x: x["match_score"], reverse=True)
        return scored[:top_k]
