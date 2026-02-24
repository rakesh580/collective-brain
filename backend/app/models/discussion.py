from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from app.db.database import Base


class DiscussionThread(Base):
    __tablename__ = "discussion_threads"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    created_by_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="open")  # "open" or "closed"
    context_type = Column(String, nullable=True)  # "member", "insight", or None (standalone)
    context_id = Column(String, nullable=True)  # ID of the related member/insight
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DiscussionMessage(Base):
    __tablename__ = "discussion_messages"

    id = Column(String, primary_key=True)
    thread_id = Column(String, ForeignKey("discussion_threads.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    edited_at = Column(DateTime, nullable=True)
    parent_message_id = Column(String, ForeignKey("discussion_messages.id"), nullable=True)
