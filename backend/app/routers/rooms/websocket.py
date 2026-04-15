"""Room WebSocket endpoint for real-time messaging and presence."""

import asyncio
import contextlib
import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect

from app.models.room import ChatRoom, ChatRoomMember, ChatRoomMessage

from ._shared import (
    _broadcast,
    _broadcast_local,
    _get_db,
    _get_online_list,
    _get_user_info,
    _msg_to_dict,
    _online_users,
    _redis_service,
    _ws_connections,
    router,
)

logger = logging.getLogger("collective_brain.rooms")


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

        from app.config import get_settings
        from app.services.auth_service import AuthService

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

    # Limit concurrent WebSocket connections per user per room
    _MAX_WS_PER_USER = 5
    user_connections_in_room = sum(1 for _, uid, _ in _ws_connections.get(room_id, []) if uid == user_id)
    if user_connections_in_room >= _MAX_WS_PER_USER:
        await websocket.close(code=4008, reason="Too many connections")
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
    await _broadcast(
        room_id,
        {
            "type": "presence",
            "online_users": _get_online_list(room_id),
            "user_joined": user_id,
            "username": username,
        },
    )

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
            except TimeoutError:
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
                    await _broadcast(
                        room_id,
                        {
                            "type": "typing",
                            "user_id": user_id,
                            "username": username,
                        },
                    )

                elif msg_type == "typing_stop":
                    await _broadcast(
                        room_id,
                        {
                            "type": "typing_stop",
                            "user_id": user_id,
                        },
                    )

                elif msg_type == "message":
                    # Save and broadcast message via WebSocket (with retry)
                    content = data.get("content", "").strip()
                    if not content:
                        continue
                    # Enforce message length limit
                    if len(content) > 10000:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": "Message too long (max 10,000 characters).",
                            }
                        )
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
                                created_at=datetime.now(UTC),
                            )
                            db.add(msg)
                            room.message_count = (room.message_count or 0) + 1
                            room.last_message_at = datetime.now(UTC)
                            db.commit()

                            await _broadcast(
                                room_id,
                                {
                                    "type": "new_message",
                                    "message": _msg_to_dict(msg),
                                },
                            )
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
                        with contextlib.suppress(Exception):
                            await websocket.send_json(
                                {
                                    "type": "error",
                                    "message": "Failed to save message. Please try again.",
                                }
                            )

                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("Room WS error: user=%s room=%s err=%s", user_id, room_id, e)
    finally:
        # Always clean up connection state — wrap each step in try/except
        # to ensure one failure doesn't prevent subsequent cleanup
        try:
            if entry in _ws_connections.get(room_id, []):
                _ws_connections[room_id].remove(entry)
        except Exception:
            pass

        # Only remove from online if no other connections for this user
        try:
            still_connected = any(uid == user_id for _, uid, _ in _ws_connections.get(room_id, []))
            if not still_connected:
                _online_users[room_id].discard(user_id)
        except Exception:
            pass

        # Unsubscribe from Redis and clean up if last connection in this room
        try:
            if not _ws_connections.get(room_id):
                if redis and redis.is_connected:
                    await redis.unsubscribe(channel)
                    logger.info("Unsubscribed from Redis channel: %s", channel)
                # Clean up empty connection lists to prevent memory leak
                _ws_connections.pop(room_id, None)
                _online_users.pop(room_id, None)
        except Exception:
            pass

        logger.info("Room WS disconnected: user=%s room=%s", user_id, room_id)

        with contextlib.suppress(Exception):
            await _broadcast(
                room_id,
                {
                    "type": "presence",
                    "online_users": _get_online_list(room_id),
                    "user_left": user_id,
                    "username": username,
                },
            )
