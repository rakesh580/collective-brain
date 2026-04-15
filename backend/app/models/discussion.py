from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class DiscussionThread(Base):
    __tablename__ = "discussion_threads"

    id = Column(String, primary_key=True)
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title = Column(String, nullable=False)
    created_by_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, default="open")  # "open" or "closed"
    context_type = Column(String, nullable=True)  # "member", "insight", or None (standalone)
    context_id = Column(String, nullable=True)  # ID of the related member/insight
    room_id = Column(String, ForeignKey("chat_rooms.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    messages = relationship(
        "DiscussionMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DiscussionMessage(Base):
    __tablename__ = "discussion_messages"

    id = Column(String, primary_key=True)
    thread_id = Column(String, ForeignKey("discussion_threads.id", ondelete="CASCADE"), index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    edited_at = Column(DateTime, nullable=True)
    parent_message_id = Column(String, ForeignKey("discussion_messages.id"), nullable=True)

    thread = relationship("DiscussionThread", back_populates="messages")
