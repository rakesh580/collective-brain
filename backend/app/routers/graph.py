import logging

from fastapi import APIRouter, HTTPException, Request

from app.schemas.responses import GraphResponse
from app.services.memory_graph import MemoryGraph
from app.db.database import get_session

logger = logging.getLogger("collective_brain.graph")

router = APIRouter()


def _get_db():
    return next(get_session())


@router.get("/full", response_model=GraphResponse)
async def get_full_graph(request: Request):
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        graph = MemoryGraph(db)
        nodes, edges = graph.build_full_graph()
        return GraphResponse(nodes=nodes, edges=edges)
    except Exception as e:
        logger.error("Graph build failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to build graph")
    finally:
        db.close()


@router.get("/member/{member_id}", response_model=GraphResponse)
async def get_member_graph(member_id: str, request: Request):
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        graph = MemoryGraph(db)
        nodes, edges = graph.get_member_subgraph(member_id)
        return GraphResponse(nodes=nodes, edges=edges)
    except Exception as e:
        logger.error("Member graph failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to build member graph")
    finally:
        db.close()


@router.get("/topic/{topic}", response_model=GraphResponse)
async def get_topic_graph(topic: str, request: Request):
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        graph = MemoryGraph(db)
        nodes, edges = graph.get_topic_subgraph(topic)
        return GraphResponse(nodes=nodes, edges=edges)
    except Exception as e:
        logger.error("Topic graph failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to build topic graph")
    finally:
        db.close()


@router.get("/expertise-matrix")
async def get_expertise_matrix(request: Request):
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        graph = MemoryGraph(db)
        return graph.get_expertise_matrix()
    except Exception as e:
        logger.error("Expertise matrix failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to build expertise matrix")
    finally:
        db.close()
