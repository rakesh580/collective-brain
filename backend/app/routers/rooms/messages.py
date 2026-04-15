"""Room message endpoints: send and list messages."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, Request

from app.models.room import ChatRoom, ChatRoomMember, ChatRoomMessage
from app.schemas.requests import RoomMessageRequest

from ._shared import _broadcast, _get_db, _msg_to_dict, router


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
            created_at=datetime.now(UTC),
        )
        db.add(msg)
        room.message_count = (room.message_count or 0) + 1
        room.last_message_at = datetime.now(UTC)
        room.updated_at = datetime.now(UTC)
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
