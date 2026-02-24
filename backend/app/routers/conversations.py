from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import IntegrityError

from app.models.conversation import ConversationRecord, MessageRecord, ConversationParticipant
from app.models.user import UserRecord
from app.schemas.requests import ShareConversationRequest
from app.db.database import get_session

router = APIRouter()


def _get_db():
    return next(get_session())


@router.get("")
async def list_conversations(request: Request, limit: int = 20, offset: int = 0):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        participant_conv_ids = [
            p.conversation_id
            for p in db.query(ConversationParticipant.conversation_id)
            .filter(ConversationParticipant.user_id == user.id)
            .all()
        ]
        query = db.query(ConversationRecord).filter(
            (ConversationRecord.owner_user_id == user.id)
            | (ConversationRecord.id.in_(participant_conv_ids))
            | (ConversationRecord.visibility == "team")
        )
        total = query.count()
        conversations = (
            query.order_by(ConversationRecord.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "conversations": [
                {
                    "id": c.id,
                    "title": c.title,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                    "message_count": c.message_count or 0,
                    "visibility": c.visibility or "private",
                    "owner_user_id": c.owner_user_id,
                }
                for c in conversations
            ],
            "total": total,
        }
    finally:
        db.close()


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        conv = (
            db.query(ConversationRecord)
            .filter(ConversationRecord.id == conversation_id)
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Access check: owner, participant, team-visible, or legacy (no owner)
        if conv.owner_user_id and conv.owner_user_id != user.id and conv.visibility != "team":
            is_participant = (
                db.query(ConversationParticipant)
                .filter(
                    ConversationParticipant.conversation_id == conversation_id,
                    ConversationParticipant.user_id == user.id,
                )
                .first()
            )
            if not is_participant:
                raise HTTPException(status_code=403, detail="Not authorized to view this conversation")

        messages = (
            db.query(MessageRecord)
            .filter(MessageRecord.conversation_id == conversation_id)
            .order_by(MessageRecord.created_at.asc())
            .all()
        )
        return {
            "id": conv.id,
            "title": conv.title,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            "visibility": conv.visibility or "private",
            "owner_user_id": conv.owner_user_id,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "sources": m.sources or [],
                    "related_members": m.related_members or [],
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "sender_user_id": m.sender_user_id,
                    "sender_name": m.sender_name,
                }
                for m in messages
            ],
        }
    finally:
        db.close()


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str, request: Request):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        conv = (
            db.query(ConversationRecord)
            .filter(ConversationRecord.id == conversation_id)
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Only owner or legacy conversations (no owner) can be deleted
        if conv.owner_user_id and conv.owner_user_id != user.id:
            raise HTTPException(status_code=403, detail="Only the owner can delete this conversation")

        db.query(ConversationParticipant).filter(
            ConversationParticipant.conversation_id == conversation_id
        ).delete()
        db.query(MessageRecord).filter(
            MessageRecord.conversation_id == conversation_id
        ).delete()
        db.delete(conv)
        db.commit()
        return {"status": "deleted"}
    finally:
        db.close()


@router.post("/{conversation_id}/share")
async def share_conversation(
    conversation_id: str, body: ShareConversationRequest, request: Request
):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    db = _get_db()
    try:
        conv = (
            db.query(ConversationRecord)
            .filter(ConversationRecord.id == conversation_id)
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conv.owner_user_id and conv.owner_user_id != user.id:
            raise HTTPException(status_code=403, detail="Only the owner can share")

        for uid in body.user_ids:
            try:
                db.add(
                    ConversationParticipant(
                        id=str(uuid4()),
                        conversation_id=conversation_id,
                        user_id=uid,
                        role="participant",
                    )
                )
                db.flush()
            except IntegrityError:
                db.rollback()  # Duplicate — already a participant, skip
        conv.visibility = "shared"
        db.commit()
        return {"status": "shared", "conversation_id": conversation_id}
    finally:
        db.close()


@router.get("/{conversation_id}/participants")
async def list_participants(conversation_id: str, request: Request):
    from app.dependencies import get_current_user

    get_current_user(request)
    db = _get_db()
    try:
        participants = (
            db.query(ConversationParticipant)
            .filter(ConversationParticipant.conversation_id == conversation_id)
            .all()
        )
        result = []
        for p in participants:
            u = db.query(UserRecord).filter(UserRecord.id == p.user_id).first()
            if u:
                result.append(
                    {
                        "user_id": u.id,
                        "username": u.username,
                        "display_name": u.display_name,
                        "role": p.role,
                        "joined_at": p.joined_at.isoformat() if p.joined_at else None,
                    }
                )
        return result
    finally:
        db.close()


@router.delete("/{conversation_id}/participants/{user_id}")
async def remove_participant(conversation_id: str, user_id: str, request: Request):
    from app.dependencies import get_current_user

    current_user = get_current_user(request)
    db = _get_db()
    try:
        conv = (
            db.query(ConversationRecord)
            .filter(ConversationRecord.id == conversation_id)
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if current_user.id != conv.owner_user_id and current_user.id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        db.query(ConversationParticipant).filter(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == user_id,
        ).delete()
        db.commit()
        return {"status": "removed"}
    finally:
        db.close()
