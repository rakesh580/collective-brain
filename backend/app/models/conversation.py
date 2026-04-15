from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.database import Base


class ConversationRecord(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    message_count = Column(Integer, default=0)
    metadata_json = Column(JSON, default=dict)
    owner_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    visibility = Column(String, default="private")  # "private", "shared", "team"
    room_id = Column(String, ForeignKey("chat_rooms.id"), nullable=True, index=True)

    owner = relationship("UserRecord", back_populates="conversations")
    messages = relationship(
        "MessageRecord",
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class MessageRecord(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    sources = Column(JSON, default=list)  # serialized SourceRef list
    related_members = Column(JSON, default=list)  # serialized RelatedMember list
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    sender_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    sender_name = Column(String, nullable=True)

    conversation = relationship("ConversationRecord", back_populates="messages")


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"
    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_participant_conv_user"),
    )

    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role = Column(String, default="participant")  # "owner" or "participant"
    joined_at = Column(DateTime, default=lambda: datetime.now(UTC))
