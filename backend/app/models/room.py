from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id = Column(String, primary_key=True)
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_by_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    avatar_color = Column(String, default="from-indigo-500 to-violet-500")
    is_archived = Column(Boolean, default=False)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    last_message_at = Column(DateTime, nullable=True)
    message_count = Column(Integer, default=0)

    members = relationship(
        "ChatRoomMember",
        back_populates="room",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    room_messages = relationship(
        "ChatRoomMessage",
        back_populates="room",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ChatRoomMember(Base):
    __tablename__ = "chat_room_members"

    id = Column(String, primary_key=True)
    room_id = Column(String, ForeignKey("chat_rooms.id", ondelete="CASCADE"), index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    role = Column(String, default="member")  # "admin" or "member"
    joined_at = Column(DateTime, default=lambda: datetime.now(UTC))
    last_read_at = Column(DateTime, nullable=True)

    room = relationship("ChatRoom", back_populates="members")


class ChatRoomMessage(Base):
    __tablename__ = "chat_room_messages"

    id = Column(String, primary_key=True)
    room_id = Column(String, ForeignKey("chat_rooms.id", ondelete="CASCADE"), index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)  # null for AI messages
    sender_name = Column(String, nullable=False)
    message_type = Column(String, default="user")  # "user", "ai", "system"
    content = Column(Text, nullable=False)
    sources = Column(JSON, default=list)  # AI message sources
    related_members = Column(JSON, default=list)  # AI message related members
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    edited_at = Column(DateTime, nullable=True)
    parent_message_id = Column(String, ForeignKey("chat_room_messages.id"), nullable=True)

    room = relationship("ChatRoom", back_populates="room_messages")
