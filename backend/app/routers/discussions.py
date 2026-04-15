import json
import logging
from collections import defaultdict
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select

from app.db.database import create_session
from app.models.discussion import DiscussionMessage, DiscussionThread
from app.models.user import UserRecord
from app.schemas.requests import (
    CreateDiscussionMessageRequest,
    CreateThreadRequest,
    EditDiscussionMessageRequest,
)

logger = logging.getLogger("collective_brain.discussions")

router = APIRouter()

# Local WebSocket connections: thread_id -> list of WebSocket
# Each server process tracks its own connections.
_ws_connections: dict[str, list[WebSocket]] = defaultdict(list)

# Reference to Redis service (set during startup via app.state)
_redis_service = None


def init_redis_from_app(app):
    """Called at startup to set the Redis reference without needing a request."""
    global _redis_service
    _redis_service = getattr(app.state, "redis", None)


def _get_db():
    return create_session()


def _get_user_info(db, user_id: str) -> dict:
    u = db.query(UserRecord).filter(UserRecord.id == user_id).first()
    if u:
        return {"username": u.username, "display_name": u.display_name}
    return {"username": "unknown", "display_name": None}


def _msg_to_dict(msg: DiscussionMessage, db) -> dict:
    info = _get_user_info(db, msg.user_id)
    return {
        "id": msg.id,
        "thread_id": msg.thread_id,
        "user_id": msg.user_id,
        "username": info["username"],
        "display_name": info["display_name"],
        "content": msg.content,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
        "parent_message_id": msg.parent_message_id,
    }


async def _broadcast_local(thread_id: str, event: dict):
    """Send event to all WebSocket connections in THIS process."""
    connections = _ws_connections.get(thread_id, [])
    dead = []
    for ws in list(connections):  # iterate a copy to avoid mutation during iteration
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        try:
            connections.remove(ws)
        except ValueError:
            pass  # already removed by another coroutine


async def _broadcast(thread_id: str, event: dict):
    """Broadcast event via Redis pub/sub (multi-process) or locally.

    When Redis is available:
      Publish to Redis channel "discussion:{thread_id}".
      Each process's subscriber delivers to its local WebSocket connections.

    When Redis is unavailable:
      Deliver directly to local connections (single-process mode).
    """
    redis = _redis_service
    if redis and redis.is_connected:
        await redis.publish(f"discussion:{thread_id}", event)
    else:
        await _broadcast_local(thread_id, event)


@router.post("")
async def create_thread(body: CreateThreadRequest, request: Request):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        thread = DiscussionThread(
            id=str(uuid4()),
            title=body.title,
            created_by_user_id=user.id,
            context_type=body.context_type,
            context_id=body.context_id,
            room_id=body.room_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(thread)
        db.commit()
        info = _get_user_info(db, user.id)
        return {
            "id": thread.id,
            "title": thread.title,
            "created_by_user_id": user.id,
            "created_by_username": info["username"],
            "created_by_display_name": info["display_name"],
            "status": thread.status,
            "context_type": thread.context_type,
            "context_id": thread.context_id,
            "message_count": 0,
            "created_at": thread.created_at.isoformat(),
            "updated_at": thread.updated_at.isoformat(),
        }
    finally:
        db.close()


@router.get("")
async def list_threads(
    request: Request,
    context_type: str | None = None,
    context_id: str | None = None,
    status: str | None = None,
    room_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        # Subquery: message count per thread
        msg_count_sq = (
            select(
                DiscussionMessage.thread_id,
                func.count(DiscussionMessage.id).label("msg_count"),
            )
            .group_by(DiscussionMessage.thread_id)
            .subquery()
        )

        # Build base query with JOIN for author info and message count
        query = (
            db.query(
                DiscussionThread,
                UserRecord.username.label("author_username"),
                UserRecord.display_name.label("author_display_name"),
                msg_count_sq.c.msg_count,
            )
            .join(UserRecord, UserRecord.id == DiscussionThread.created_by_user_id)
            .outerjoin(msg_count_sq, msg_count_sq.c.thread_id == DiscussionThread.id)
        )

        if room_id:
            query = query.filter(DiscussionThread.room_id == room_id)
        if context_type:
            query = query.filter(DiscussionThread.context_type == context_type)
        if context_id:
            query = query.filter(DiscussionThread.context_id == context_id)
        if status:
            query = query.filter(DiscussionThread.status == status)

        total = query.count()
        rows = (
            query.order_by(DiscussionThread.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        result = []
        for t, author_username, author_display_name, msg_count in rows:
            result.append({
                "id": t.id,
                "title": t.title,
                "created_by_user_id": t.created_by_user_id,
                "created_by_username": author_username or "unknown",
                "created_by_display_name": author_display_name,
                "status": t.status,
                "context_type": t.context_type,
                "context_id": t.context_id,
                "message_count": msg_count or 0,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            })

        return {"threads": result, "total": total}
    finally:
        db.close()


@router.get("/{thread_id}")
async def get_thread(thread_id: str, request: Request):
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        thread = (
            db.query(DiscussionThread)
            .filter(DiscussionThread.id == thread_id)
            .first()
        )
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        info = _get_user_info(db, thread.created_by_user_id)
        messages = (
            db.query(DiscussionMessage)
            .filter(DiscussionMessage.thread_id == thread_id)
            .order_by(DiscussionMessage.created_at.asc())
            .all()
        )

        return {
            "id": thread.id,
            "title": thread.title,
            "created_by_user_id": thread.created_by_user_id,
            "created_by_username": info["username"],
            "created_by_display_name": info["display_name"],
            "status": thread.status,
            "context_type": thread.context_type,
            "context_id": thread.context_id,
            "message_count": len(messages),
            "created_at": thread.created_at.isoformat() if thread.created_at else None,
            "updated_at": thread.updated_at.isoformat() if thread.updated_at else None,
            "messages": [_msg_to_dict(m, db) for m in messages],
        }
    finally:
        db.close()


@router.post("/{thread_id}/messages")
async def add_message(
    thread_id: str, body: CreateDiscussionMessageRequest, request: Request
):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        thread = (
            db.query(DiscussionThread)
            .filter(DiscussionThread.id == thread_id)
            .first()
        )
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        msg = DiscussionMessage(
            id=str(uuid4()),
            thread_id=thread_id,
            user_id=user.id,
            content=body.content,
            parent_message_id=body.parent_message_id,
            created_at=datetime.now(UTC),
        )
        db.add(msg)
        thread.updated_at = datetime.now(UTC)
        db.commit()

        msg_dict = _msg_to_dict(msg, db)

        # Broadcast to WebSocket clients
        await _broadcast(thread_id, {"type": "new_message", "message": msg_dict})

        return msg_dict
    finally:
        db.close()


@router.put("/{thread_id}/messages/{message_id}")
async def edit_message(
    thread_id: str,
    message_id: str,
    body: EditDiscussionMessageRequest,
    request: Request,
):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        msg = (
            db.query(DiscussionMessage)
            .filter(
                DiscussionMessage.id == message_id,
                DiscussionMessage.thread_id == thread_id,
            )
            .first()
        )
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        if msg.user_id != user.id:
            raise HTTPException(status_code=403, detail="Can only edit your own messages")

        msg.content = body.content
        msg.edited_at = datetime.now(UTC)
        db.commit()

        msg_dict = _msg_to_dict(msg, db)
        await _broadcast(thread_id, {"type": "message_edited", "message": msg_dict})

        return msg_dict
    finally:
        db.close()


@router.delete("/{thread_id}/messages/{message_id}")
async def delete_message(thread_id: str, message_id: str, request: Request):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        msg = (
            db.query(DiscussionMessage)
            .filter(
                DiscussionMessage.id == message_id,
                DiscussionMessage.thread_id == thread_id,
            )
            .first()
        )
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        if msg.user_id != user.id:
            raise HTTPException(status_code=403, detail="Can only delete your own messages")

        db.delete(msg)
        db.commit()

        await _broadcast(
            thread_id,
            {"type": "message_deleted", "message_id": message_id},
        )

        return {"status": "deleted"}
    finally:
        db.close()


@router.websocket("/ws/{thread_id}")
async def discussion_websocket(websocket: WebSocket, thread_id: str):
    await websocket.accept()

    # Authenticate via first message: {"token": "..."}
    try:
        first = await websocket.receive_text()
        data = json.loads(first)
        token = data.get("token")
        if not token:
            await websocket.close(code=4001, reason="Token required")
            return

        from app.config import get_settings
        from app.services.auth_service import AuthService

        settings = get_settings()
        auth_svc = AuthService(settings)
        user_id = auth_svc.decode_token(token)
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except (json.JSONDecodeError, Exception):
        await websocket.close(code=4001, reason="Auth failed")
        return

    # Verify thread exists before allowing connection
    db = _get_db()
    try:
        thread = (
            db.query(DiscussionThread)
            .filter(DiscussionThread.id == thread_id)
            .first()
        )
        if not thread:
            await websocket.close(code=4004, reason="Thread not found")
            return
    finally:
        db.close()

    # Register connection
    _ws_connections[thread_id].append(websocket)
    logger.info("WS connected: user=%s thread=%s", user_id, thread_id)

    # Subscribe to Redis channel for this thread (multi-process delivery)
    redis = _redis_service
    channel = f"discussion:{thread_id}"
    is_first_in_thread = len(_ws_connections[thread_id]) == 1

    if redis and redis.is_connected and is_first_in_thread:
        async def _on_redis_message(data: dict):
            """Deliver Redis pub/sub messages to local WebSocket connections."""
            await _broadcast_local(thread_id, data)

        await redis.subscribe(channel, _on_redis_message)
        logger.info("Subscribed to Redis channel: %s", channel)

    try:
        while True:
            # Keep connection alive; we don't process client messages beyond auth
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _ws_connections.get(thread_id, []):
            _ws_connections[thread_id].remove(websocket)

        # Unsubscribe from Redis and clean up if last connection in this thread
        if not _ws_connections.get(thread_id):
            if redis and redis.is_connected:
                await redis.unsubscribe(channel)
                logger.info("Unsubscribed from Redis channel: %s", channel)
            # Clean up empty connection lists to prevent memory leak
            _ws_connections.pop(thread_id, None)

        logger.info("WS disconnected: user=%s thread=%s", user_id, thread_id)
