"""Initial schema — all tables as of current models.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-03-16

This captures the complete schema state including all columns that were
previously added via hand-rolled ALTER TABLE statements in database.py.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- members (no FKs, must come first) ---
    op.create_table(
        "members",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("aliases", sa.JSON(), server_default="[]"),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("expertise_tags", sa.JSON(), server_default="[]"),
        sa.Column("expertise_scores", sa.JSON(), server_default="{}"),
        sa.Column("strengths", sa.JSON(), server_default="[]"),
        sa.Column("weaknesses", sa.JSON(), server_default="[]"),
        sa.Column("first_seen", sa.DateTime(), nullable=True),
        sa.Column("last_active", sa.DateTime(), nullable=True),
        sa.Column("total_contributions", sa.Float(), server_default="0"),
        sa.Column("metadata_json", sa.JSON(), server_default="{}"),
    )

    # --- users (FK -> members) ---
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column("linked_member_id", sa.String(), sa.ForeignKey("members.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("google_id", sa.String(), nullable=True),
        sa.Column("auth_provider", sa.String(), nullable=True, server_default="local"),
        sa.Column("reset_code", sa.String(), nullable=True),
        sa.Column("reset_code_expires", sa.DateTime(), nullable=True),
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
        sa.Column("skills", sa.JSON(), server_default="[]"),
        sa.Column("role_title", sa.String(), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)

    # --- chat_rooms (FK -> users) ---
    op.create_table(
        "chat_rooms",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("avatar_color", sa.String(), server_default="from-indigo-500 to-violet-500"),
        sa.Column("is_archived", sa.Boolean(), server_default="0"),
        sa.Column("is_public", sa.Boolean(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("message_count", sa.Integer(), server_default="0"),
    )

    # --- chat_room_members (FK -> chat_rooms, users) ---
    op.create_table(
        "chat_room_members",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("room_id", sa.String(), sa.ForeignKey("chat_rooms.id"), nullable=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("role", sa.String(), server_default="member"),
        sa.Column("joined_at", sa.DateTime(), nullable=True),
        sa.Column("last_read_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_chat_room_members_room_id", "chat_room_members", ["room_id"])
    op.create_index("ix_chat_room_members_user_id", "chat_room_members", ["user_id"])

    # --- chat_room_messages (FK -> chat_rooms, users, self) ---
    op.create_table(
        "chat_room_messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("room_id", sa.String(), sa.ForeignKey("chat_rooms.id"), nullable=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("sender_name", sa.String(), nullable=False),
        sa.Column("message_type", sa.String(), server_default="user"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), server_default="[]"),
        sa.Column("related_members", sa.JSON(), server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("edited_at", sa.DateTime(), nullable=True),
        sa.Column("parent_message_id", sa.String(), sa.ForeignKey("chat_room_messages.id"), nullable=True),
    )
    op.create_index("ix_chat_room_messages_room_id", "chat_room_messages", ["room_id"])

    # --- artifacts (FK -> chat_rooms) ---
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_path", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), server_default="0"),
        sa.Column("member_ids", sa.JSON(), server_default="[]"),
        sa.Column("metadata_json", sa.JSON(), server_default="{}"),
        sa.Column("status", sa.String(), server_default="completed"),
        sa.Column("room_id", sa.String(), sa.ForeignKey("chat_rooms.id"), nullable=True),
    )
    op.create_index("ix_artifacts_room_id", "artifacts", ["room_id"])

    # --- contributions (FK -> members, artifacts, chat_rooms) ---
    op.create_table(
        "contributions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("member_id", sa.String(), sa.ForeignKey("members.id"), nullable=True),
        sa.Column("artifact_id", sa.String(), sa.ForeignKey("artifacts.id"), nullable=True),
        sa.Column("contribution_type", sa.String(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("topics", sa.JSON(), server_default="[]"),
        sa.Column("sentiment", sa.Float(), nullable=True),
        sa.Column("impact_score", sa.Float(), server_default="0.0"),
        sa.Column("metadata_json", sa.JSON(), server_default="{}"),
        sa.Column("room_id", sa.String(), sa.ForeignKey("chat_rooms.id"), nullable=True),
    )
    op.create_index("ix_contributions_room_id", "contributions", ["room_id"])

    # --- conversations (FK -> users, chat_rooms) ---
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("message_count", sa.Integer(), server_default="0"),
        sa.Column("metadata_json", sa.JSON(), server_default="{}"),
        sa.Column("owner_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("visibility", sa.String(), server_default="private"),
        sa.Column("room_id", sa.String(), sa.ForeignKey("chat_rooms.id"), nullable=True),
    )
    op.create_index("ix_conversations_room_id", "conversations", ["room_id"])

    # --- messages (FK -> conversations, users) ---
    op.create_table(
        "messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("conversation_id", sa.String(), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), server_default="[]"),
        sa.Column("related_members", sa.JSON(), server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("sender_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("sender_name", sa.String(), nullable=True),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    # --- conversation_participants (FK -> conversations, users) ---
    op.create_table(
        "conversation_participants",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("conversation_id", sa.String(), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("role", sa.String(), server_default="participant"),
        sa.Column("joined_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("conversation_id", "user_id", name="uq_participant_conv_user"),
    )
    op.create_index("ix_conversation_participants_conversation_id", "conversation_participants", ["conversation_id"])
    op.create_index("ix_conversation_participants_user_id", "conversation_participants", ["user_id"])

    # --- discussion_threads (FK -> users, chat_rooms) ---
    op.create_table(
        "discussion_threads",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(), server_default="open"),
        sa.Column("context_type", sa.String(), nullable=True),
        sa.Column("context_id", sa.String(), nullable=True),
        sa.Column("room_id", sa.String(), sa.ForeignKey("chat_rooms.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_discussion_threads_room_id", "discussion_threads", ["room_id"])

    # --- discussion_messages (FK -> discussion_threads, users, self) ---
    op.create_table(
        "discussion_messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("thread_id", sa.String(), sa.ForeignKey("discussion_threads.id"), nullable=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("edited_at", sa.DateTime(), nullable=True),
        sa.Column("parent_message_id", sa.String(), sa.ForeignKey("discussion_messages.id"), nullable=True),
    )
    op.create_index("ix_discussion_messages_thread_id", "discussion_messages", ["thread_id"])

    # --- slack_workspaces (FK -> users) ---
    op.create_table(
        "slack_workspaces",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("team_name", sa.String(), nullable=False),
        sa.Column("bot_token", sa.Text(), nullable=False),
        sa.Column("bot_user_id", sa.String(), nullable=True),
        sa.Column("installed_by_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("installed_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1"),
        sa.Column("metadata_json", sa.JSON(), server_default="{}"),
    )

    # --- slack_channel_syncs (FK -> slack_workspaces, chat_rooms) ---
    op.create_table(
        "slack_channel_syncs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("slack_workspaces.id"), nullable=False),
        sa.Column("slack_channel_id", sa.String(), nullable=False),
        sa.Column("slack_channel_name", sa.String(), nullable=True),
        sa.Column("room_id", sa.String(), sa.ForeignKey("chat_rooms.id"), nullable=True),
        sa.Column("sync_mode", sa.String(), server_default="ingest"),
        sa.Column("is_active", sa.Boolean(), server_default="1"),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("last_message_ts", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), server_default="{}"),
    )

    # --- insights (FK -> chat_rooms) ---
    op.create_table(
        "insights",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("insight_type", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column("related_member_ids", sa.JSON(), server_default="[]"),
        sa.Column("confidence", sa.Float(), server_default="0.0"),
        sa.Column("period_start", sa.DateTime(), nullable=True),
        sa.Column("period_end", sa.DateTime(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), server_default="{}"),
        sa.Column("room_id", sa.String(), sa.ForeignKey("chat_rooms.id"), nullable=True),
    )
    op.create_index("ix_insights_room_id", "insights", ["room_id"])

    # --- help_requests (raw SQL table, no ORM model) ---
    op.create_table(
        "help_requests",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("requester_user_id", sa.String(), nullable=False),
        sa.Column("expert_member_id", sa.String(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("topics", sa.Text(), server_default="[]"),
        sa.Column("status", sa.String(), server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )

    # --- slack_digest_config (raw SQL table, no ORM model) ---
    op.create_table(
        "slack_digest_config",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("channel_id", sa.String(), nullable=False),
        sa.Column("channel_name", sa.String(), server_default=""),
        sa.Column("schedule_day", sa.Integer(), server_default="0"),
        sa.Column("schedule_hour", sa.Integer(), server_default="9"),
        sa.Column("enabled", sa.Integer(), server_default="1"),
        sa.Column("last_sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # --- health_snapshots (raw SQL table, no ORM model) ---
    op.create_table(
        "health_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("bus_factor_count", sa.Integer(), server_default="0"),
        sa.Column("coverage_pct", sa.Float(), server_default="0"),
        sa.Column("collab_density", sa.Float(), server_default="0"),
        sa.Column("active_member_pct", sa.Float(), server_default="0"),
        sa.Column("avg_breadth", sa.Float(), server_default="0"),
        sa.Column("health_score", sa.Float(), server_default="0"),
        sa.Column("risk_summary", sa.Text(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("health_snapshots")
    op.drop_table("slack_digest_config")
    op.drop_table("help_requests")
    op.drop_table("insights")
    op.drop_table("slack_channel_syncs")
    op.drop_table("slack_workspaces")
    op.drop_table("discussion_messages")
    op.drop_table("discussion_threads")
    op.drop_table("conversation_participants")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("contributions")
    op.drop_table("artifacts")
    op.drop_table("chat_room_messages")
    op.drop_table("chat_room_members")
    op.drop_table("chat_rooms")
    op.drop_table("users")
    op.drop_table("members")
