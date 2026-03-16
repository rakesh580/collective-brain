from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, ForeignKey, UniqueConstraint
from app.db.database import Base


class ConversationRecord(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    message_count = Column(Integer, default=0)
    metadata_json = Column(JSON, default=dict)
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    visibility = Column(String, default="private")  # "private", "shared", "team"
    room_id = Column(String, ForeignKey("chat_rooms.id"), nullable=True, index=True)


class MessageRecord(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), index=True)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    sources = Column(JSON, default=list)  # serialized SourceRef list
    related_members = Column(JSON, default=list)  # serialized RelatedMember list
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sender_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    sender_name = Column(String, nullable=True)


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"
    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_participant_conv_user"),
    )

    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    role = Column(String, default="participant")  # "owner" or "participant"
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
