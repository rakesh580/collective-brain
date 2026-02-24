import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

from app.db.database import get_session
from app.models.room import ChatRoom, ChatRoomMember, ChatRoomMessage
from app.models.user import UserRecord
from app.schemas.requests import (
    CreateRoomRequest,
    UpdateRoomRequest,
    AddRoomMembersRequest,
    RoomMessageRequest,
    RoomAIQueryRequest,
)

logger = logging.getLogger("collective_brain.rooms")

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
    return next(get_session())


def _get_redis(request: Request = None):
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
        return {"username": u.username, "display_name": u.display_name}
    return {"username": "unknown", "display_name": None}


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


# ─── REST Endpoints ───────────────────────────────────────────


@router.post("", status_code=201)
async def create_room(body: CreateRoomRequest, request: Request):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        # Pick avatar color from room name hash
        name_hash = sum(ord(c) for c in body.name)
        avatar_color = AVATAR_COLORS[name_hash % len(AVATAR_COLORS)]

        room = ChatRoom(
            id=str(uuid4()),
            name=body.name,
            description=body.description,
            created_by_user_id=user.id,
            avatar_color=avatar_color,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(room)

        # Add creator as admin
        admin_member = ChatRoomMember(
            id=str(uuid4()),
            room_id=room.id,
            user_id=user.id,
            role="admin",
            joined_at=datetime.utcnow(),
        )
        db.add(admin_member)

        # Add invited members
        for uid in body.member_user_ids:
            if uid == user.id:
                continue
            u = db.query(UserRecord).filter(UserRecord.id == uid).first()
            if u:
                member = ChatRoomMember(
                    id=str(uuid4()),
                    room_id=room.id,
                    user_id=uid,
                    role="member",
                    joined_at=datetime.utcnow(),
                )
                db.add(member)

        # Add system message
        sys_msg = ChatRoomMessage(
            id=str(uuid4()),
            room_id=room.id,
            user_id=None,
            sender_name="System",
            message_type="system",
            content=f"{user.display_name or user.username} created the room",
            created_at=datetime.utcnow(),
        )
        db.add(sys_msg)
        room.message_count = 1

        db.commit()

        info = _get_user_info(db, user.id)
        member_count = (
            db.query(ChatRoomMember)
            .filter(ChatRoomMember.room_id == room.id)
            .count()
        )

        return {
            "id": room.id,
            "name": room.name,
            "description": room.description,
            "created_by_user_id": user.id,
            "created_by_username": info["username"],
            "avatar_color": room.avatar_color,
            "member_count": member_count,
            "message_count": room.message_count,
            "last_message_at": None,
            "last_message_preview": sys_msg.content,
            "created_at": room.created_at.isoformat(),
        }
    finally:
        db.close()


@router.get("")
async def list_rooms(request: Request, limit: int = 50, offset: int = 0):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        # Get rooms where user is a member
        user_room_ids = (
            db.query(ChatRoomMember.room_id)
            .filter(ChatRoomMember.user_id == user.id)
            .subquery()
        )

        rooms = (
            db.query(ChatRoom)
            .filter(ChatRoom.id.in_(user_room_ids))
            .filter(ChatRoom.is_archived == False)  # noqa: E712
            .order_by(ChatRoom.last_message_at.desc().nullslast(), ChatRoom.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        result = []
        for room in rooms:
            info = _get_user_info(db, room.created_by_user_id)
            member_count = (
                db.query(ChatRoomMember)
                .filter(ChatRoomMember.room_id == room.id)
                .count()
            )

            # Get last message preview
            last_msg = (
                db.query(ChatRoomMessage)
                .filter(ChatRoomMessage.room_id == room.id)
                .order_by(ChatRoomMessage.created_at.desc())
                .first()
            )

            result.append({
                "id": room.id,
                "name": room.name,
                "description": room.description,
                "created_by_user_id": room.created_by_user_id,
                "created_by_username": info["username"],
                "avatar_color": room.avatar_color,
                "member_count": member_count,
                "message_count": room.message_count or 0,
                "last_message_at": room.last_message_at.isoformat() if room.last_message_at else None,
                "last_message_preview": (
                    f"{last_msg.sender_name}: {last_msg.content[:80]}"
                    if last_msg
                    else None
                ),
                "created_at": room.created_at.isoformat() if room.created_at else None,
            })

        return {"rooms": result}
    finally:
        db.close()


@router.get("/{room_id}")
async def get_room(room_id: str, request: Request):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")

        # Check membership
        membership = (
            db.query(ChatRoomMember)
            .filter(
                ChatRoomMember.room_id == room_id,
                ChatRoomMember.user_id == user.id,
            )
            .first()
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this room")

        info = _get_user_info(db, room.created_by_user_id)

        # Get members
        members_q = (
            db.query(ChatRoomMember)
            .filter(ChatRoomMember.room_id == room_id)
            .all()
        )
        online_set = _online_users.get(room_id, set())
        members = []
        for m in members_q:
            u_info = _get_user_info(db, m.user_id)
            members.append({
                "user_id": m.user_id,
                "username": u_info["username"],
                "display_name": u_info["display_name"],
                "role": m.role,
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
                "is_online": m.user_id in online_set,
            })

        # Get messages (last 100)
        messages = (
            db.query(ChatRoomMessage)
            .filter(ChatRoomMessage.room_id == room_id)
            .order_by(ChatRoomMessage.created_at.asc())
            .limit(100)
            .all()
        )

        # Update last_read_at
        membership.last_read_at = datetime.utcnow()
        db.commit()

        return {
            "id": room.id,
            "name": room.name,
            "description": room.description,
            "created_by_user_id": room.created_by_user_id,
            "created_by_username": info["username"],
            "avatar_color": room.avatar_color,
            "member_count": len(members),
            "message_count": room.message_count or 0,
            "last_message_at": room.last_message_at.isoformat() if room.last_message_at else None,
            "created_at": room.created_at.isoformat() if room.created_at else None,
            "members": members,
            "messages": [_msg_to_dict(m) for m in messages],
        }
    finally:
        db.close()


@router.put("/{room_id}")
async def update_room(room_id: str, body: UpdateRoomRequest, request: Request):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")

        # Only admin can update
        membership = (
            db.query(ChatRoomMember)
            .filter(
                ChatRoomMember.room_id == room_id,
                ChatRoomMember.user_id == user.id,
                ChatRoomMember.role == "admin",
            )
            .first()
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Only admins can update rooms")

        if body.name is not None:
            room.name = body.name
        if body.description is not None:
            room.description = body.description
        room.updated_at = datetime.utcnow()
        db.commit()

        return {"status": "updated"}
    finally:
        db.close()


@router.post("/{room_id}/members")
async def add_members(room_id: str, body: AddRoomMembersRequest, request: Request):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")

        # Check user is a member
        membership = (
            db.query(ChatRoomMember)
            .filter(
                ChatRoomMember.room_id == room_id,
                ChatRoomMember.user_id == user.id,
            )
            .first()
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this room")

        added = []
        for uid in body.user_ids:
            # Check not already member
            existing = (
                db.query(ChatRoomMember)
                .filter(
                    ChatRoomMember.room_id == room_id,
                    ChatRoomMember.user_id == uid,
                )
                .first()
            )
            if existing:
                continue

            u = db.query(UserRecord).filter(UserRecord.id == uid).first()
            if not u:
                continue

            member = ChatRoomMember(
                id=str(uuid4()),
                room_id=room_id,
                user_id=uid,
                role="member",
                joined_at=datetime.utcnow(),
            )
            db.add(member)
            added.append(u.display_name or u.username)

        if added:
            # System message
            sys_msg = ChatRoomMessage(
                id=str(uuid4()),
                room_id=room_id,
                user_id=None,
                sender_name="System",
                message_type="system",
                content=f"{user.display_name or user.username} added {', '.join(added)}",
                created_at=datetime.utcnow(),
            )
            db.add(sys_msg)
            room.message_count = (room.message_count or 0) + 1
            room.last_message_at = datetime.utcnow()
            db.commit()

            await _broadcast(room_id, {
                "type": "new_message",
                "message": _msg_to_dict(sys_msg),
            })
            await _broadcast(room_id, {
                "type": "members_changed",
            })

        return {"added": len(added)}
    finally:
        db.close()


@router.delete("/{room_id}/members/{user_id}")
async def remove_member(room_id: str, user_id: str, request: Request):
    from app.dependencies import get_current_user

    current_user = get_current_user(request)
    db = _get_db()
    try:
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")

        # Admins can remove anyone, members can leave
        requester_membership = (
            db.query(ChatRoomMember)
            .filter(
                ChatRoomMember.room_id == room_id,
                ChatRoomMember.user_id == current_user.id,
            )
            .first()
        )
        if not requester_membership:
            raise HTTPException(status_code=403, detail="Not a member of this room")

        if current_user.id != user_id and requester_membership.role != "admin":
            raise HTTPException(status_code=403, detail="Only admins can remove members")

        target = (
            db.query(ChatRoomMember)
            .filter(
                ChatRoomMember.room_id == room_id,
                ChatRoomMember.user_id == user_id,
            )
            .first()
        )
        if not target:
            raise HTTPException(status_code=404, detail="Member not found in room")

        target_info = _get_user_info(db, user_id)
        db.delete(target)

        action = "left" if current_user.id == user_id else "was removed by " + (current_user.display_name or current_user.username)
        sys_msg = ChatRoomMessage(
            id=str(uuid4()),
            room_id=room_id,
            user_id=None,
            sender_name="System",
            message_type="system",
            content=f"{target_info['display_name'] or target_info['username']} {action}",
            created_at=datetime.utcnow(),
        )
        db.add(sys_msg)
        room.message_count = (room.message_count or 0) + 1
        room.last_message_at = datetime.utcnow()
        db.commit()

        await _broadcast(room_id, {
            "type": "new_message",
            "message": _msg_to_dict(sys_msg),
        })
        await _broadcast(room_id, {"type": "members_changed"})

        return {"status": "removed"}
    finally:
        db.close()


@router.post("/{room_id}/messages")
async def send_message(room_id: str, body: RoomMessageRequest, request: Request):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")

        membership = (
            db.query(ChatRoomMember)
            .filter(
                ChatRoomMember.room_id == room_id,
                ChatRoomMember.user_id == user.id,
            )
            .first()
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this room")

        msg = ChatRoomMessage(
            id=str(uuid4()),
            room_id=room_id,
            user_id=user.id,
            sender_name=user.display_name or user.username,
            message_type="user",
            content=body.content,
            parent_message_id=body.parent_message_id,
            created_at=datetime.utcnow(),
        )
        db.add(msg)
        room.message_count = (room.message_count or 0) + 1
        room.last_message_at = datetime.utcnow()
        room.updated_at = datetime.utcnow()
        db.commit()

        msg_dict = _msg_to_dict(msg)

        # Broadcast to all room WebSocket connections
        await _broadcast(room_id, {
            "type": "new_message",
            "message": msg_dict,
        })

        return msg_dict
    finally:
        db.close()


@router.post("/{room_id}/ai")
async def ai_query(room_id: str, body: RoomAIQueryRequest, request: Request):
    """Trigger AI agent response in room. The AI reads team member data and responds."""
    from app.dependencies import get_current_user

    user = get_current_user(request)

    # Rate limit: 10 AI queries per minute per user
    redis = getattr(request.app.state, "redis", None)
    if redis:
        allowed, _ = await redis.check_rate_limit(f"ai:room:{user.id}", 10, 60)
        if not allowed:
            raise HTTPException(status_code=429, detail="AI query rate limit exceeded. Please wait a moment.")

    db = _get_db()
    try:
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")

        membership = (
            db.query(ChatRoomMember)
            .filter(
                ChatRoomMember.room_id == room_id,
                ChatRoomMember.user_id == user.id,
            )
            .first()
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this room")

        # Save user's question as a room message
        user_msg = ChatRoomMessage(
            id=str(uuid4()),
            room_id=room_id,
            user_id=user.id,
            sender_name=user.display_name or user.username,
            message_type="user",
            content=body.question,
            created_at=datetime.utcnow(),
        )
        db.add(user_msg)
        room.message_count = (room.message_count or 0) + 1
        room.last_message_at = datetime.utcnow()
        db.commit()

        # Broadcast user's question
        await _broadcast(room_id, {
            "type": "new_message",
            "message": _msg_to_dict(user_msg),
        })

        # Send typing indicator for AI
        await _broadcast(room_id, {
            "type": "typing",
            "user_id": "ai-agent",
            "username": "AI Agent",
        })

        # Run AI pipeline
        settings = request.app.state.settings
        if settings.agent_mode == "langgraph":
            from app.services.agent_pipeline import AgentPipeline
            pipeline = AgentPipeline(
                db=db,
                settings=settings,
                embedder=request.app.state.embedding_service,
                vector_store=request.app.state.vector_store,
            )
        else:
            from app.services.rag_pipeline import RAGPipeline
            pipeline = RAGPipeline(
                llm=request.app.state.llm_service,
                embedder=request.app.state.embedding_service,
                vector_store=request.app.state.vector_store,
                db=db,
            )

        # Build room context: recent messages for context
        recent_msgs = (
            db.query(ChatRoomMessage)
            .filter(
                ChatRoomMessage.room_id == room_id,
                ChatRoomMessage.message_type != "system",
            )
            .order_by(ChatRoomMessage.created_at.desc())
            .limit(20)
            .all()
        )
        recent_msgs.reverse()

        room_context = "\n".join(
            f"{m.sender_name}: {m.content}" for m in recent_msgs
        )

        # Enrich question with room context
        enriched_question = (
            f"[Group chat context - Room: {room.name}]\n"
            f"Recent conversation:\n{room_context}\n\n"
            f"{user.display_name or user.username} asks: {body.question}"
        )

        result = await pipeline.answer(
            question=enriched_question,
            conversation_id=None,  # Don't mix with 1:1 conversations
            filters=None,
            sender_user_id=user.id,
            sender_name=user.display_name or user.username,
        )

        # Save AI response as room message
        ai_msg = ChatRoomMessage(
            id=str(uuid4()),
            room_id=room_id,
            user_id=None,
            sender_name="AI Agent",
            message_type="ai",
            content=result.answer,
            sources=[s.model_dump() for s in result.sources] if result.sources else [],
            related_members=[m.model_dump() for m in result.related_members] if result.related_members else [],
            created_at=datetime.utcnow(),
        )
        db.add(ai_msg)
        room.message_count = (room.message_count or 0) + 1
        room.last_message_at = datetime.utcnow()
        db.commit()

        ai_msg_dict = _msg_to_dict(ai_msg)

        # Broadcast AI response
        await _broadcast(room_id, {
            "type": "new_message",
            "message": ai_msg_dict,
        })

        # Clear typing indicator
        await _broadcast(room_id, {
            "type": "typing_stop",
            "user_id": "ai-agent",
        })

        return ai_msg_dict
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI query failed in room %s: %s", room_id, str(e), exc_info=True)
        # Send error as system message (visible in room)
        try:
            error_msg = ChatRoomMessage(
                id=str(uuid4()),
                room_id=room_id,
                user_id=None,
                sender_name="System",
                message_type="system",
                content="AI agent encountered an error. Please try again.",
                created_at=datetime.utcnow(),
            )
            db.add(error_msg)
            room.message_count = (room.message_count or 0) + 1
            db.commit()

            await _broadcast(room_id, {
                "type": "new_message",
                "message": _msg_to_dict(error_msg),
            })
        except Exception:
            logger.error("Failed to save error message in room %s", room_id)

        await _broadcast(room_id, {
            "type": "typing_stop",
            "user_id": "ai-agent",
        })

        raise HTTPException(status_code=500, detail="AI query failed")
    finally:
        db.close()


@router.get("/{room_id}/messages")
async def get_messages(
    room_id: str,
    request: Request,
    limit: int = 50,
    before: str | None = None,
):
    """Get paginated messages. Use 'before' for infinite scroll (pass earliest message ID)."""
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        membership = (
            db.query(ChatRoomMember)
            .filter(
                ChatRoomMember.room_id == room_id,
                ChatRoomMember.user_id == user.id,
            )
            .first()
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this room")

        query = db.query(ChatRoomMessage).filter(
            ChatRoomMessage.room_id == room_id
        )

        if before:
            ref_msg = (
                db.query(ChatRoomMessage)
                .filter(ChatRoomMessage.id == before)
                .first()
            )
            if ref_msg:
                query = query.filter(
                    ChatRoomMessage.created_at < ref_msg.created_at
                )

        messages = (
            query.order_by(ChatRoomMessage.created_at.desc())
            .limit(limit)
            .all()
        )
        messages.reverse()

        return {"messages": [_msg_to_dict(m) for m in messages]}
    finally:
        db.close()


# ─── WebSocket Endpoint ───────────────────────────────────────


@router.websocket("/ws/{room_id}")
async def room_websocket(websocket: WebSocket, room_id: str):
    await websocket.accept()

    user_id = None
    username = None

    # Authenticate via first message: {"token": "..."}
    try:
        first = await websocket.receive_text()
        data = json.loads(first)
        token = data.get("token")
        if not token:
            await websocket.close(code=4001, reason="Token required")
            return

        from app.services.auth_service import AuthService
        from app.config import get_settings

        settings = get_settings()
        auth_svc = AuthService(settings)
        user_id = auth_svc.decode_token(token)
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return

        # Verify room membership
        db = _get_db()
        try:
            membership = (
                db.query(ChatRoomMember)
                .filter(
                    ChatRoomMember.room_id == room_id,
                    ChatRoomMember.user_id == user_id,
                )
                .first()
            )
            if not membership:
                await websocket.close(code=4003, reason="Not a member of this room")
                return

            user_info = _get_user_info(db, user_id)
            username = user_info["display_name"] or user_info["username"]
        finally:
            db.close()

    except (json.JSONDecodeError, Exception):
        await websocket.close(code=4001, reason="Auth failed")
        return

    # Register connection
    entry = (websocket, user_id, username)
    _ws_connections[room_id].append(entry)
    _online_users[room_id].add(user_id)

    logger.info("Room WS connected: user=%s room=%s", user_id, room_id)

    # Subscribe to Redis channel for this room (multi-process delivery)
    redis = _redis_service
    channel = f"room:{room_id}"
    is_first_in_room = len(_ws_connections[room_id]) == 1

    if redis and redis.is_connected and is_first_in_room:
        async def _on_redis_message(data: dict):
            """Deliver Redis pub/sub messages to local WebSocket connections."""
            await _broadcast_local(room_id, data)

        await redis.subscribe(channel, _on_redis_message)
        logger.info("Subscribed to Redis channel: %s", channel)

    # Broadcast presence update
    await _broadcast(room_id, {
        "type": "presence",
        "online_users": _get_online_list(room_id),
        "user_joined": user_id,
        "username": username,
    })

    # Periodic membership re-check interval (seconds).
    # If a user is removed from the room, their WS is closed within this window.
    _MEMBERSHIP_CHECK_INTERVAL = 30

    try:
        while True:
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=_MEMBERSHIP_CHECK_INTERVAL,
                )
            except asyncio.TimeoutError:
                # No message received — re-check membership
                db = _get_db()
                try:
                    still_member = (
                        db.query(ChatRoomMember)
                        .filter(
                            ChatRoomMember.room_id == room_id,
                            ChatRoomMember.user_id == user_id,
                        )
                        .first()
                    )
                finally:
                    db.close()
                if not still_member:
                    await websocket.close(code=4003, reason="Removed from room")
                    break
                continue

            try:
                data = json.loads(raw)
                msg_type = data.get("type")

                if msg_type == "typing":
                    # Broadcast typing indicator to other users
                    await _broadcast(room_id, {
                        "type": "typing",
                        "user_id": user_id,
                        "username": username,
                    })

                elif msg_type == "typing_stop":
                    await _broadcast(room_id, {
                        "type": "typing_stop",
                        "user_id": user_id,
                    })

                elif msg_type == "message":
                    # Save and broadcast message via WebSocket (with retry)
                    content = data.get("content", "").strip()
                    if not content:
                        continue

                    saved = False
                    for attempt in range(2):
                        db = _get_db()
                        try:
                            room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
                            if not room:
                                break

                            msg = ChatRoomMessage(
                                id=str(uuid4()),
                                room_id=room_id,
                                user_id=user_id,
                                sender_name=username,
                                message_type="user",
                                content=content,
                                parent_message_id=data.get("parent_message_id"),
                                created_at=datetime.utcnow(),
                            )
                            db.add(msg)
                            room.message_count = (room.message_count or 0) + 1
                            room.last_message_at = datetime.utcnow()
                            db.commit()

                            await _broadcast(room_id, {
                                "type": "new_message",
                                "message": _msg_to_dict(msg),
                            })
                            saved = True
                            break
                        except Exception as db_err:
                            db.rollback()
                            if attempt == 0:
                                logger.warning("DB write failed (attempt 1), retrying: %s", db_err)
                            else:
                                logger.error("DB write failed after retry: %s", db_err)
                        finally:
                            db.close()

                    if not saved:
                        try:
                            await websocket.send_json({
                                "type": "error",
                                "message": "Failed to save message. Please try again.",
                            })
                        except Exception:
                            pass

                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        pass
    finally:
        if entry in _ws_connections.get(room_id, []):
            _ws_connections[room_id].remove(entry)

        # Only remove from online if no other connections for this user
        still_connected = any(
            uid == user_id for _, uid, _ in _ws_connections.get(room_id, [])
        )
        if not still_connected:
            _online_users[room_id].discard(user_id)

        # Unsubscribe from Redis and clean up if last connection in this room
        if not _ws_connections.get(room_id):
            if redis and redis.is_connected:
                await redis.unsubscribe(channel)
                logger.info("Unsubscribed from Redis channel: %s", channel)
            # Clean up empty connection lists to prevent memory leak
            _ws_connections.pop(room_id, None)
            _online_users.pop(room_id, None)

        logger.info("Room WS disconnected: user=%s room=%s", user_id, room_id)

        await _broadcast(room_id, {
            "type": "presence",
            "online_users": _get_online_list(room_id),
            "user_left": user_id,
            "username": username,
        })
