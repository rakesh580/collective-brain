from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, ForeignKey, Boolean
from app.db.database import Base


class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_by_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    avatar_color = Column(String, default="from-indigo-500 to-violet-500")
    is_archived = Column(Boolean, default=False)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at = Column(DateTime, nullable=True)
    message_count = Column(Integer, default=0)


class ChatRoomMember(Base):
    __tablename__ = "chat_room_members"

    id = Column(String, primary_key=True)
    room_id = Column(String, ForeignKey("chat_rooms.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    role = Column(String, default="member")  # "admin" or "member"
    joined_at = Column(DateTime, default=datetime.utcnow)
    last_read_at = Column(DateTime, nullable=True)


class ChatRoomMessage(Base):
    __tablename__ = "chat_room_messages"

    id = Column(String, primary_key=True)
    room_id = Column(String, ForeignKey("chat_rooms.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)  # null for AI messages
    sender_name = Column(String, nullable=False)
    message_type = Column(String, default="user")  # "user", "ai", "system"
    content = Column(Text, nullable=False)
    sources = Column(JSON, default=list)  # AI message sources
    related_members = Column(JSON, default=list)  # AI message related members
    created_at = Column(DateTime, default=datetime.utcnow)
    edited_at = Column(DateTime, nullable=True)
    parent_message_id = Column(String, ForeignKey("chat_room_messages.id"), nullable=True)
