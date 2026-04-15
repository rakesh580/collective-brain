"""Room CRUD endpoints: create, list, discover, join, get, update."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlalchemy import func, select

from app.models.room import ChatRoom, ChatRoomMember, ChatRoomMessage
from app.models.user import UserRecord
from app.schemas.requests import CreateRoomRequest, UpdateRoomRequest

from ._shared import (
    AVATAR_COLORS,
    _broadcast,
    _get_db,
    _get_user_info,
    _msg_to_dict,
    _online_users,
    router,
)


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
            is_public=body.is_public if body.is_public is not None else False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(room)

        # Add creator as admin
        admin_member = ChatRoomMember(
            id=str(uuid4()),
            room_id=room.id,
            user_id=user.id,
            role="admin",
            joined_at=datetime.now(UTC),
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
                    joined_at=datetime.now(UTC),
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
            created_at=datetime.now(UTC),
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

        # Subquery: member count per room
        member_count_sq = (
            select(
                ChatRoomMember.room_id,
                func.count(ChatRoomMember.id).label("member_count"),
            )
            .group_by(ChatRoomMember.room_id)
            .subquery()
        )

        # Subquery: latest message per room (using a correlated subquery for max created_at)
        latest_msg_time_sq = (
            select(
                ChatRoomMessage.room_id,
                func.max(ChatRoomMessage.created_at).label("max_created_at"),
            )
            .group_by(ChatRoomMessage.room_id)
            .subquery()
        )

        # Join latest message time back to get the actual message row
        latest_msg_sq = (
            select(
                ChatRoomMessage.room_id,
                ChatRoomMessage.sender_name,
                ChatRoomMessage.content,
            )
            .join(
                latest_msg_time_sq,
                (ChatRoomMessage.room_id == latest_msg_time_sq.c.room_id)
                & (ChatRoomMessage.created_at == latest_msg_time_sq.c.max_created_at),
            )
            .subquery()
        )

        # Total count (before pagination)
        total = (
            db.query(func.count(ChatRoom.id))
            .filter(ChatRoom.id.in_(user_room_ids))
            .filter(ChatRoom.is_archived == False)  # noqa: E712
            .scalar()
        )

        # Single query: rooms + creator info + member count + last message
        rows = (
            db.query(
                ChatRoom,
                UserRecord.username.label("creator_username"),
                member_count_sq.c.member_count,
                latest_msg_sq.c.sender_name.label("last_sender"),
                latest_msg_sq.c.content.label("last_content"),
            )
            .join(UserRecord, UserRecord.id == ChatRoom.created_by_user_id)
            .outerjoin(member_count_sq, member_count_sq.c.room_id == ChatRoom.id)
            .outerjoin(latest_msg_sq, latest_msg_sq.c.room_id == ChatRoom.id)
            .filter(ChatRoom.id.in_(user_room_ids))
            .filter(ChatRoom.is_archived == False)  # noqa: E712
            .order_by(ChatRoom.last_message_at.desc().nullslast(), ChatRoom.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        result = []
        for room, creator_username, member_count, last_sender, last_content in rows:
            last_preview = None
            if last_sender and last_content:
                last_preview = f"{last_sender}: {last_content[:80]}"

            result.append({
                "id": room.id,
                "name": room.name,
                "description": room.description,
                "created_by_user_id": room.created_by_user_id,
                "created_by_username": creator_username or "unknown",
                "avatar_color": room.avatar_color,
                "member_count": member_count or 0,
                "message_count": room.message_count or 0,
                "last_message_at": room.last_message_at.isoformat() if room.last_message_at else None,
                "last_message_preview": last_preview,
                "created_at": room.created_at.isoformat() if room.created_at else None,
            })

        return {"rooms": result, "total": total}
    finally:
        db.close()


@router.get("/discover")
async def discover_rooms(request: Request, q: str | None = None, limit: int = 50, offset: int = 0):
    """Discover public rooms that the user is not already a member of."""
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        # Get rooms user is already in
        user_room_ids = [
            rid for (rid,) in
            db.query(ChatRoomMember.room_id)
            .filter(ChatRoomMember.user_id == user.id)
            .all()
        ]

        query = (
            db.query(ChatRoom)
            .filter(ChatRoom.is_public == True)  # noqa: E712
            .filter(ChatRoom.is_archived == False)  # noqa: E712
        )
        if user_room_ids:
            query = query.filter(~ChatRoom.id.in_(user_room_ids))
        if q:
            q_lower = f"%{q.lower()}%"
            query = query.filter(
                ChatRoom.name.ilike(q_lower) | ChatRoom.description.ilike(q_lower)
            )

        total = query.count()
        rooms = (
            query.order_by(ChatRoom.created_at.desc())
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
            result.append({
                "id": room.id,
                "name": room.name,
                "description": room.description,
                "created_by_user_id": room.created_by_user_id,
                "created_by_username": info["username"],
                "avatar_color": room.avatar_color,
                "is_public": room.is_public,
                "member_count": member_count,
                "created_at": room.created_at.isoformat() if room.created_at else None,
            })

        return {"rooms": result, "total": total}
    finally:
        db.close()


@router.post("/{room_id}/join")
async def join_room(room_id: str, request: Request):
    """Join a public room (self-service)."""
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        if not room.is_public:
            raise HTTPException(status_code=403, detail="This room is not public. Ask an admin to invite you.")

        # Check if already a member
        existing = (
            db.query(ChatRoomMember)
            .filter(
                ChatRoomMember.room_id == room_id,
                ChatRoomMember.user_id == user.id,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="Already a member of this room")

        member = ChatRoomMember(
            id=str(uuid4()),
            room_id=room_id,
            user_id=user.id,
            role="member",
            joined_at=datetime.now(UTC),
        )
        db.add(member)

        # System message
        sys_msg = ChatRoomMessage(
            id=str(uuid4()),
            room_id=room_id,
            user_id=None,
            sender_name="System",
            message_type="system",
            content=f"{user.display_name or user.username} joined the room",
            created_at=datetime.now(UTC),
        )
        db.add(sys_msg)
        room.message_count = (room.message_count or 0) + 1
        room.last_message_at = datetime.now(UTC)
        db.commit()

        await _broadcast(room_id, {
            "type": "new_message",
            "message": _msg_to_dict(sys_msg),
        })
        await _broadcast(room_id, {"type": "members_changed"})

        return {"status": "joined", "room_id": room_id}
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
                "skills": u_info.get("skills", []),
                "role_title": u_info.get("role_title"),
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
        membership.last_read_at = datetime.now(UTC)
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
        if body.is_public is not None:
            room.is_public = body.is_public
        room.updated_at = datetime.now(UTC)
        db.commit()

        return {"status": "updated"}
    finally:
        db.close()
