"""Room AI query endpoint: trigger AI agent responses in a room."""

import logging
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, Request

from app.models.room import ChatRoom, ChatRoomMember, ChatRoomMessage
from app.models.user import UserRecord
from app.schemas.requests import RoomAIQueryRequest

from ._shared import _broadcast, _get_db, _msg_to_dict, router

logger = logging.getLogger("collective_brain.rooms")


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
            created_at=datetime.now(UTC),
        )
        db.add(user_msg)
        room.message_count = (room.message_count or 0) + 1
        room.last_message_at = datetime.now(UTC)
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

        # Build room member skills context
        room_member_users = (
            db.query(UserRecord)
            .join(ChatRoomMember, ChatRoomMember.user_id == UserRecord.id)
            .filter(ChatRoomMember.room_id == room_id)
            .all()
        )
        skills_lines = []
        for u in room_member_users:
            skills = u.skills or []
            if skills or u.role_title:
                name = u.display_name or u.username
                role = f" ({u.role_title})" if u.role_title else ""
                skill_str = ", ".join(skills) if skills else "none declared"
                skills_lines.append(f"- {name}{role}: skills=[{skill_str}]")
        skills_context = "\n".join(skills_lines) if skills_lines else ""

        # Enrich question with room context
        skills_block = f"Room member skills:\n{skills_context}\n\n" if skills_context else ""
        enriched_question = (
            f"[Group chat context - Room: {room.name}]\n"
            f"{skills_block}"
            f"Recent conversation:\n{room_context}\n\n"
            f"{user.display_name or user.username} asks: {body.question}"
        )

        result = await pipeline.answer(
            question=enriched_question,
            conversation_id=None,  # Don't mix with 1:1 conversations
            filters=None,
            sender_user_id=user.id,
            sender_name=user.display_name or user.username,
            room_id=room_id,
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
            created_at=datetime.now(UTC),
        )
        db.add(ai_msg)
        room.message_count = (room.message_count or 0) + 1
        room.last_message_at = datetime.now(UTC)
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
                created_at=datetime.now(UTC),
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
