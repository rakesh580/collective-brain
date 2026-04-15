"""Three-layer knowledge graph: Social, Artifact, Concept.

Layers:
  Social   -- Member nodes + COLLABORATED_WITH edges
  Artifact -- ArtifactRecord nodes + CONTRIBUTED_TO edges (member -> artifact)
  Concept  -- Topic nodes + KNOWS_ABOUT / COVERS_TOPIC / HAS_EXPERTISE / DECLARED_SKILL edges

Features:
  - NetworkX in-memory graph with cache invalidation
  - Temporal decay on edges so recent contributions weigh more
  - User-declared skills integrated as topic nodes
  - PageRank, betweenness centrality, community detection
"""

from sqlalchemy.orm import Session

from .builder import invalidate_graph_cache, GraphBuilderMixin
from .query import GraphQueryMixin
from .analysis import GraphAnalysisMixin


class MemoryGraph(GraphBuilderMixin, GraphQueryMixin, GraphAnalysisMixin):
    """Build and query a three-layer knowledge graph backed by NetworkX."""

    def __init__(self, db: Session, *, redis=None, room_id: str | None = None):
        self.db = db
        self._redis = redis
        self.room_id = room_id


__all__ = ["MemoryGraph", "invalidate_graph_cache"]
