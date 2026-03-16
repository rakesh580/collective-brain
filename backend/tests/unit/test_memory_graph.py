"""Unit tests for MemoryGraph — graph building, subgraphs, pattern detection."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.services.memory_graph import MemoryGraph


class TestGraphBuilding:
    def test_empty_database(self, db_session):
        graph = MemoryGraph(db_session)
        nodes, edges = graph.build_full_graph()
        assert nodes == []
        assert edges == []

    def test_builds_member_nodes(self, db_session, seed_members):
        graph = MemoryGraph(db_session)
        nodes, edges = graph.build_full_graph()
        member_nodes = [n for n in nodes if n.type == "member"]
        assert len(member_nodes) == 3

    def test_builds_artifact_nodes(self, db_session, seed_members, seed_artifacts):
        graph = MemoryGraph(db_session)
        nodes, edges = graph.build_full_graph()
        artifact_nodes = [n for n in nodes if n.type == "artifact"]
        assert len(artifact_nodes) >= 1

    def test_builds_contribution_edges(self, db_session, seed_members, seed_artifacts):
        graph = MemoryGraph(db_session)
        nodes, edges = graph.build_full_graph()
        contrib_edges = [e for e in edges if e.type == "CONTRIBUTED_TO"]
        assert len(contrib_edges) > 0

    def test_builds_topic_nodes(self, db_session, seed_members, seed_artifacts):
        graph = MemoryGraph(db_session)
        nodes, edges = graph.build_full_graph()
        topic_nodes = [n for n in nodes if n.type == "topic"]
        # Members have expertise tags and contributions have topics
        assert len(topic_nodes) > 0

    def test_collaboration_edges(self, db_session, seed_members, seed_artifacts):
        graph = MemoryGraph(db_session)
        nodes, edges = graph.build_full_graph()
        collab_edges = [e for e in edges if e.type == "COLLABORATED_WITH"]
        # alice and bob share artifacts
        assert len(collab_edges) >= 1


class TestSubgraphs:
    def test_member_subgraph(self, db_session, seed_members, seed_artifacts):
        graph = MemoryGraph(db_session)
        nodes, edges = graph.get_member_subgraph("alice")
        # Should include alice and her connected nodes
        member_ids = [n.id for n in nodes if n.type == "member"]
        assert "alice" in member_ids

    def test_member_subgraph_nonexistent(self, db_session, seed_members):
        graph = MemoryGraph(db_session)
        nodes, edges = graph.get_member_subgraph("nobody")
        assert len(nodes) == 0

    def test_topic_subgraph(self, db_session, seed_members, seed_artifacts):
        graph = MemoryGraph(db_session)
        nodes, edges = graph.get_topic_subgraph("python")
        # Should find members with python expertise
        assert len(nodes) >= 1


class TestExpertiseScoring:
    def test_expertise_matrix(self, db_session, seed_members, seed_artifacts):
        graph = MemoryGraph(db_session)
        matrix = graph.get_expertise_matrix()
        assert "members" in matrix
        assert "topics" in matrix
        # Each member entry should have scores
        for member in matrix["members"]:
            assert "scores" in member

    def test_compute_expertise_scores(self, db_session, seed_members, seed_artifacts):
        graph = MemoryGraph(db_session)
        scores = graph.compute_expertise_scores("alice")
        assert isinstance(scores, dict)
        # alice has contributions with topics ["python", "api"]
        assert len(scores) > 0


class TestPatternDetection:
    def test_detect_patterns_returns_list(self, db_session, seed_members, seed_artifacts):
        graph = MemoryGraph(db_session)
        patterns = graph.detect_patterns()
        assert isinstance(patterns, list)

    def test_detect_patterns_empty_db(self, db_session):
        graph = MemoryGraph(db_session)
        patterns = graph.detect_patterns()
        assert isinstance(patterns, list)

    def test_bus_factor_detection(self, db_session):
        """A topic with only one contributor should trigger bus factor risk."""
        from app.models.member import MemberRecord
        from app.models.artifact import ArtifactRecord
        from app.models.contribution import ContributionRecord

        member = MemberRecord(
            id="lone-dev",
            name="Lone Dev",
            expertise_tags=["niche-topic"],
            total_contributions=10,
            last_active=datetime.now(timezone.utc),
        )
        db_session.add(member)

        art = ArtifactRecord(
            id="solo-art",
            source_type="git",
            source_path="/solo",
            chunk_count=1,
            member_ids=["lone-dev"],
            status="completed",
        )
        db_session.add(art)

        contrib = ContributionRecord(
            id=str(uuid4()),
            member_id="lone-dev",
            artifact_id="solo-art",
            contribution_type="git_content",
            timestamp=datetime.now(timezone.utc),
            description="solo work",
            topics=["niche-topic"],
        )
        db_session.add(contrib)
        db_session.commit()

        graph = MemoryGraph(db_session)
        patterns = graph.detect_patterns()
        # The pattern type is "risk" not "bus_factor_risk"
        bus_factor = [p for p in patterns if "bus factor" in p.get("title", "").lower()]
        assert len(bus_factor) >= 1

    def test_stale_expertise_detection(self, db_session):
        """A member inactive > 90 days should trigger stale expertise."""
        from app.models.member import MemberRecord
        from app.models.contribution import ContributionRecord

        member = MemberRecord(
            id="stale-dev",
            name="Stale Dev",
            expertise_tags=["old-tech"],
            total_contributions=10,
            last_active=datetime.now(timezone.utc) - timedelta(days=120),
        )
        db_session.add(member)

        # Stale expertise needs actual contributions (checked via ContributionRecord)
        # with timestamps > 90 days old AND total_contributions > 3
        contrib = ContributionRecord(
            id=str(uuid4()),
            member_id="stale-dev",
            artifact_id=None,
            contribution_type="git_content",
            timestamp=datetime.now(timezone.utc) - timedelta(days=120),
            description="old work",
            topics=["old-tech"],
        )
        db_session.add(contrib)
        db_session.commit()

        graph = MemoryGraph(db_session)
        patterns = graph.detect_patterns()
        stale = [p for p in patterns if "stale" in p.get("title", "").lower()]
        assert len(stale) >= 1
