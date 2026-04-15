import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.schemas.responses import GraphResponse
from app.services.memory_graph import MemoryGraph
from app.db.database import create_session
from app.dependencies import get_current_user

logger = logging.getLogger("collective_brain.graph")

router = APIRouter()


def _get_db():
    return create_session()


@router.get("/full", response_model=GraphResponse)
async def get_full_graph(request: Request, room_id: str | None = None, user=Depends(get_current_user)):
    db = _get_db()
    try:
        graph = MemoryGraph(db, room_id=room_id)
        nodes, edges = graph.build_full_graph()
        return GraphResponse(nodes=nodes, edges=edges)
    except Exception as e:
        logger.error("Graph build failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to build graph")
    finally:
        db.close()


@router.get("/member/{member_id}", response_model=GraphResponse)
async def get_member_graph(member_id: str, request: Request, room_id: str | None = None, user=Depends(get_current_user)):
    db = _get_db()
    try:
        graph = MemoryGraph(db, room_id=room_id)
        nodes, edges = graph.get_member_subgraph(member_id)
        return GraphResponse(nodes=nodes, edges=edges)
    except Exception as e:
        logger.error("Member graph failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to build member graph")
    finally:
        db.close()


@router.get("/topic/{topic}", response_model=GraphResponse)
async def get_topic_graph(topic: str, request: Request, room_id: str | None = None, user=Depends(get_current_user)):
    db = _get_db()
    try:
        graph = MemoryGraph(db, room_id=room_id)
        nodes, edges = graph.get_topic_subgraph(topic)
        return GraphResponse(nodes=nodes, edges=edges)
    except Exception as e:
        logger.error("Topic graph failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to build topic graph")
    finally:
        db.close()


@router.get("/stats")
async def get_graph_stats(request: Request, room_id: str | None = None, user=Depends(get_current_user)):
    db = _get_db()
    try:
        graph = MemoryGraph(db, room_id=room_id)
        return graph.get_graph_stats()
    except Exception as e:
        logger.error("Graph stats failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to compute graph stats")
    finally:
        db.close()


@router.get("/expertise-matrix")
async def get_expertise_matrix(request: Request, room_id: str | None = None, user=Depends(get_current_user)):
    db = _get_db()
    try:
        graph = MemoryGraph(db, room_id=room_id)
        return graph.get_expertise_matrix()
    except Exception as e:
        logger.error("Expertise matrix failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to build expertise matrix")
    finally:
        db.close()


@router.get("/clusters")
async def get_clusters(request: Request, room_id: str | None = None, user=Depends(get_current_user)):
    """Get detailed community/cluster information."""
    db = _get_db()
    try:
        graph = MemoryGraph(db, room_id=room_id)
        return graph.get_cluster_details()
    except Exception as e:
        logger.error("Cluster analysis failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to analyze clusters")
    finally:
        db.close()


@router.get("/expertise-gaps")
async def get_expertise_gaps(request: Request, room_id: str | None = None, user=Depends(get_current_user)):
    """Identify expertise gaps and bus factor risks."""
    db = _get_db()
    try:
        graph = MemoryGraph(db, room_id=room_id)
        return graph.get_expertise_gaps()
    except Exception as e:
        logger.error("Expertise gap analysis failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to analyze expertise gaps")
    finally:
        db.close()
