"""Slack integration models for workspace connections and channel syncing."""
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Boolean, JSON, ForeignKey
from app.db.database import Base


class SlackWorkspace(Base):
    __tablename__ = "slack_workspaces"

    id = Column(String, primary_key=True)  # Slack team_id
    team_name = Column(String, nullable=False)
    bot_token = Column(Text, nullable=False)  # encrypted in production
    bot_user_id = Column(String)
    installed_by_user_id = Column(String, ForeignKey("users.id"))
    installed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    metadata_json = Column(JSON, default=dict)


class SlackChannelSync(Base):
    __tablename__ = "slack_channel_syncs"

    id = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("slack_workspaces.id"), nullable=False)
    slack_channel_id = Column(String, nullable=False)
    slack_channel_name = Column(String)
    room_id = Column(String, ForeignKey("chat_rooms.id"), nullable=True)
    sync_mode = Column(String, default="ingest")  # ingest | mirror | bidirectional
    is_active = Column(Boolean, default=True)
    last_synced_at = Column(DateTime, nullable=True)
    last_message_ts = Column(String, nullable=True)  # Slack message timestamp for pagination
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    metadata_json = Column(JSON, default=dict)
