from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from app.db.database import Base


class UserRecord(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=True)  # nullable for OAuth-only users
    display_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    linked_member_id = Column(String, ForeignKey("members.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)
    google_id = Column(String, unique=True, nullable=True, index=True)
    auth_provider = Column(String, nullable=True, default="local")
    reset_code = Column(String, nullable=True)
    reset_code_expires = Column(DateTime, nullable=True)
    role = Column(String, nullable=False, default="member")  # "admin", "member", "viewer"
    skills = Column(JSON, default=list)
    role_title = Column(String, nullable=True)
    bio = Column(Text, nullable=True)

    conversations = relationship(
        "ConversationRecord",
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
