"""Process Slack events and bridge them to the Collective Brain ingestion pipeline."""
import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.member import MemberRecord
from app.models.contribution import ContributionRecord
from app.models.slack_integration import SlackWorkspace, SlackChannelSync
from app.services.slack_service import SlackService
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStoreService

logger = logging.getLogger("collective_brain.slack_events")

# Minimum message length to ingest (skip "ok", "thanks", etc.)
MIN_MESSAGE_LENGTH = 20


class SlackEventProcessor:
    def __init__(
        self,
        db: Session,
        slack_service: SlackService,
        embedder: EmbeddingService,
        vector_store: VectorStoreService,
    ):
        self.db = db
        self.slack = slack_service
        self.embedder = embedder
        self.vs = vector_store

    async def process_message(self, event: dict, workspace_id: str) -> bool:
        """Process a Slack message event — ingest into knowledge base."""
        # Skip bot messages, edits, and very short messages
        if event.get("subtype") in ("bot_message", "message_changed", "message_deleted"):
            return False

        text = event.get("text", "").strip()
        if len(text) < MIN_MESSAGE_LENGTH:
            return False

        channel_id = event.get("channel", "")
        user_id = event.get("user", "")
        ts = event.get("ts", "")

        # Find the channel sync config
        sync = (
            self.db.query(SlackChannelSync)
            .filter(
                SlackChannelSync.workspace_id == workspace_id,
                SlackChannelSync.slack_channel_id == channel_id,
                SlackChannelSync.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not sync:
            return False

        # Get workspace for bot token
        workspace = self.db.query(SlackWorkspace).filter(SlackWorkspace.id == workspace_id).first()
        if not workspace or not workspace.bot_token:
            return False

        # Resolve Slack user to member
        slack_user = await self.slack.get_user_info(workspace.bot_token, user_id)
        display_name = (
            slack_user.get("profile", {}).get("display_name")
            or slack_user.get("profile", {}).get("real_name")
            or slack_user.get("name", user_id)
        )
        member = self._resolve_member(display_name, slack_user)

        # Create embedding and store
        try:
            embedding = self.embedder.embed(text)
            chunk_id = f"slack-{workspace_id}-{ts}"
            timestamp = datetime.fromtimestamp(float(ts.split(".")[0]))

            metadata = {
                "source_type": "slack",
                "source_ref": f"#{sync.slack_channel_name or channel_id}",
                "artifact_id": f"slack-channel-{channel_id}",
                "author": display_name,
                "timestamp": timestamp.isoformat(),
                "topics": "",
                "room_id": sync.room_id or "",
                "slack_workspace": workspace_id,
                "slack_channel": channel_id,
                "slack_ts": ts,
            }

            self.vs.add_documents(
                ids=[chunk_id],
                documents=[text],
                embeddings=[embedding],
                metadatas=[metadata],
            )

            # Create contribution record
            contrib = ContributionRecord(
                id=str(uuid4()),
                member_id=member.id if member else None,
                artifact_id=f"slack-channel-{channel_id}",
                contribution_type="slack_message",
                timestamp=timestamp,
                description=text[:200],
                topics=[],
                room_id=sync.room_id,
            )
            self.db.add(contrib)

            # Update member activity
            if member:
                member.total_contributions = (member.total_contributions or 0) + 1
                if not member.last_active or timestamp > member.last_active:
                    member.last_active = timestamp

            # Update sync timestamp
            sync.last_synced_at = datetime.utcnow()
            sync.last_message_ts = ts

            self.db.commit()

            # Invalidate graph cache
            from app.services.memory_graph import invalidate_graph_cache
            invalidate_graph_cache(room_id=sync.room_id)

            logger.info(
                "Ingested Slack message from %s in #%s",
                display_name,
                sync.slack_channel_name or channel_id,
            )
            return True

        except Exception as e:
            logger.error("Failed to process Slack message: %s", e, exc_info=True)
            self.db.rollback()
            return False

    def _resolve_member(self, display_name: str, slack_user: dict) -> MemberRecord | None:
        """Find or create a member for a Slack user."""
        if not display_name:
            return None

        # Try name match
        member = (
            self.db.query(MemberRecord)
            .filter(MemberRecord.name.ilike(display_name))
            .first()
        )
        if member:
            return member

        # Try email match
        email = slack_user.get("profile", {}).get("email")
        if email:
            member = (
                self.db.query(MemberRecord)
                .filter(MemberRecord.email == email)
                .first()
            )
            if member:
                return member

        # Create new member
        import re
        slug = re.sub(r"[^a-z0-9]+", "-", display_name.lower()).strip("-")
        member_id = slug or str(uuid4())[:8]

        # Avoid ID collision
        if self.db.query(MemberRecord).filter(MemberRecord.id == member_id).first():
            member_id = f"{slug}-{uuid4().hex[:6]}"

        member = MemberRecord(
            id=member_id,
            name=display_name,
            aliases=[display_name.lower()],
            email=email,
            first_seen=datetime.utcnow(),
            total_contributions=0,
        )
        self.db.add(member)
        self.db.flush()
        return member

    async def process_app_mention(self, event: dict, workspace_id: str) -> str | None:
        """Handle @bot mentions — run AI query and respond."""
        text = event.get("text", "").strip()
        channel_id = event.get("channel", "")
        thread_ts = event.get("thread_ts") or event.get("ts")

        workspace = self.db.query(SlackWorkspace).filter(SlackWorkspace.id == workspace_id).first()
        if not workspace or not workspace.bot_token:
            return None

        # Strip bot mention from text
        # e.g. "<@U12345> what does Alice know about React?" -> "what does Alice know about React?"
        import re
        clean_text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
        if not clean_text:
            clean_text = "What can you help me with?"

        # Find linked room for context
        sync = (
            self.db.query(SlackChannelSync)
            .filter(
                SlackChannelSync.workspace_id == workspace_id,
                SlackChannelSync.slack_channel_id == channel_id,
                SlackChannelSync.is_active == True,  # noqa: E712
            )
            .first()
        )
        room_id = sync.room_id if sync else None

        return clean_text, room_id, workspace.bot_token, channel_id, thread_ts

    async def backfill_channel(
        self, workspace_id: str, channel_id: str, limit: int = 200
    ) -> int:
        """Backfill historical messages from a Slack channel."""
        workspace = self.db.query(SlackWorkspace).filter(SlackWorkspace.id == workspace_id).first()
        if not workspace or not workspace.bot_token:
            return 0

        messages = await self.slack.fetch_channel_history(
            workspace.bot_token, channel_id, limit=limit
        )

        ingested = 0
        for msg in messages:
            if msg.get("subtype"):
                continue
            result = await self.process_message(
                {**msg, "channel": channel_id},
                workspace_id,
            )
            if result:
                ingested += 1

        logger.info("Backfilled %d messages from channel %s", ingested, channel_id)
        return ingested
