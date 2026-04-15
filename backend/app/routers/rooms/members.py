"""Room member management endpoints: add and remove members."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, Request

from app.models.room import ChatRoom, ChatRoomMember, ChatRoomMessage
from app.models.user import UserRecord
from app.schemas.requests import AddRoomMembersRequest

from ._shared import _broadcast, _get_db, _get_user_info, _msg_to_dict, router


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
                joined_at=datetime.now(timezone.utc),
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
                created_at=datetime.now(timezone.utc),
            )
            db.add(sys_msg)
            room.message_count = (room.message_count or 0) + 1
            room.last_message_at = datetime.now(timezone.utc)
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
            created_at=datetime.now(timezone.utc),
        )
        db.add(sys_msg)
        room.message_count = (room.message_count or 0) + 1
        room.last_message_at = datetime.now(timezone.utc)
        db.commit()

        await _broadcast(room_id, {
            "type": "new_message",
            "message": _msg_to_dict(sys_msg),
        })
        await _broadcast(room_id, {"type": "members_changed"})

        return {"status": "removed"}
    finally:
        db.close()
