"""Shared state, constants, and helpers used across all room sub-modules."""

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, WebSocket

from app.db.database import create_session
from app.models.room import ChatRoom, ChatRoomMember, ChatRoomMessage
from app.models.user import UserRecord

logger = logging.getLogger("collective_brain.rooms")

# Single shared router — each sub-module imports this and adds its routes to it.
router = APIRouter()

# Local WebSocket connections: room_id -> list of (websocket, user_id, username)
# Each server process tracks its own connections.
_ws_connections: dict[str, list[tuple[WebSocket, str, str]]] = defaultdict(list)

# Track online users per room (local to this process)
_online_users: dict[str, set[str]] = defaultdict(set)

# Reference to Redis service (set during first request via app.state)
_redis_service = None

AVATAR_COLORS = [
    "from-indigo-500 to-violet-500",
    "from-emerald-500 to-teal-500",
    "from-amber-500 to-orange-500",
    "from-rose-500 to-pink-500",
    "from-cyan-500 to-blue-500",
    "from-fuchsia-500 to-purple-500",
]


def _get_db():
    return create_session()


def _get_redis(request=None):
    """Get Redis service from app state."""
    global _redis_service
    if _redis_service is None and request is not None:
        _redis_service = getattr(request.app.state, "redis", None)
    return _redis_service


def init_redis_from_app(app):
    """Called at startup to set the Redis reference without needing a request."""
    global _redis_service
    _redis_service = getattr(app.state, "redis", None)


def _get_user_info(db, user_id: str) -> dict:
    u = db.query(UserRecord).filter(UserRecord.id == user_id).first()
    if u:
        return {
            "username": u.username,
            "display_name": u.display_name,
            "skills": u.skills or [],
            "role_title": u.role_title,
        }
    return {"username": "unknown", "display_name": None, "skills": [], "role_title": None}


def _msg_to_dict(msg: ChatRoomMessage) -> dict:
    return {
        "id": msg.id,
        "room_id": msg.room_id,
        "user_id": msg.user_id,
        "sender_name": msg.sender_name,
        "message_type": msg.message_type,
        "content": msg.content,
        "sources": msg.sources or [],
        "related_members": msg.related_members or [],
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
        "parent_message_id": msg.parent_message_id,
    }


async def _broadcast_local(room_id: str, event: dict):
    """Send event to all WebSocket connections in THIS process."""
    connections = _ws_connections.get(room_id, [])
    dead = []
    for ws, uid, uname in list(connections):  # iterate a copy
        try:
            await ws.send_json(event)
        except Exception:
            dead.append((ws, uid, uname))
    for entry in dead:
        try:
            connections.remove(entry)
        except ValueError:
            pass
        _online_users[room_id].discard(entry[1])


async def _broadcast(room_id: str, event: dict):
    """Broadcast event via Redis pub/sub (multi-process) or locally.

    When Redis is available:
      Publish to Redis channel "room:{room_id}".
      Each process's subscriber delivers to its local WebSocket connections.

    When Redis is unavailable:
      Deliver directly to local connections (single-process mode).
    """
    redis = _redis_service
    if redis and redis.is_connected:
        await redis.publish(f"room:{room_id}", event)
    else:
        await _broadcast_local(room_id, event)


def _get_online_list(room_id: str) -> list[str]:
    return list(_online_users.get(room_id, set()))
