"""Slack Bot service — handles OAuth, signature verification, and message processing."""
import hashlib
import hmac
import logging
import time
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.slack_integration import SlackWorkspace

logger = logging.getLogger("collective_brain.slack")

SLACK_API_BASE = "https://slack.com/api"


class SlackService:
    def __init__(self, settings: Settings):
        self.client_id = settings.slack_client_id
        self.client_secret = settings.slack_client_secret
        self.signing_secret = settings.slack_signing_secret
        self.bot_scopes = (
            "channels:history,channels:read,chat:write,commands,"
            "groups:history,groups:read,im:history,im:read,"
            "users:read,reactions:read"
        )

    def verify_signature(self, timestamp: str, body: bytes, signature: str) -> bool:
        """Verify Slack request signature to prevent spoofing."""
        if not self.signing_secret:
            logger.warning("Slack signing secret not configured — skipping verification")
            return True

        # Reject requests older than 5 minutes (replay protection)
        if abs(time.time() - int(timestamp)) > 60 * 5:
            return False

        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        my_signature = (
            "v0="
            + hmac.new(
                self.signing_secret.encode("utf-8"),
                sig_basestring.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
        )
        return hmac.compare_digest(my_signature, signature)

    def get_install_url(self, redirect_uri: str, state: str) -> str:
        """Generate Slack OAuth install URL."""
        return (
            f"https://slack.com/oauth/v2/authorize"
            f"?client_id={self.client_id}"
            f"&scope={self.bot_scopes}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
        )

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange OAuth code for bot token."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SLACK_API_BASE}/oauth.v2.access",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                raise ValueError(f"Slack OAuth failed: {data.get('error', 'unknown')}")
            return data

    async def save_workspace(self, db: Session, oauth_data: dict, installed_by_user_id: str) -> SlackWorkspace:
        """Save or update workspace after OAuth."""
        team_id = oauth_data["team"]["id"]
        team_name = oauth_data["team"]["name"]
        bot_token = oauth_data["access_token"]
        bot_user_id = oauth_data.get("bot_user_id", "")

        existing = db.query(SlackWorkspace).filter(SlackWorkspace.id == team_id).first()
        if existing:
            existing.bot_token = bot_token
            existing.bot_user_id = bot_user_id
            existing.team_name = team_name
            existing.is_active = True
            existing.installed_by_user_id = installed_by_user_id
            db.commit()
            return existing

        workspace = SlackWorkspace(
            id=team_id,
            team_name=team_name,
            bot_token=bot_token,
            bot_user_id=bot_user_id,
            installed_by_user_id=installed_by_user_id,
            installed_at=datetime.now(UTC),
        )
        db.add(workspace)
        db.commit()
        return workspace

    async def list_channels(self, bot_token: str) -> list[dict]:
        """List channels the bot has access to."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{SLACK_API_BASE}/conversations.list",
                headers={"Authorization": f"Bearer {bot_token}"},
                params={"types": "public_channel,private_channel", "limit": 200},
            )
            data = resp.json()
            if not data.get("ok"):
                logger.error("Failed to list Slack channels: %s", data.get("error"))
                return []
            return data.get("channels", [])

    async def post_message(self, bot_token: str, channel_id: str, text: str, thread_ts: str | None = None) -> dict:
        """Post a message to a Slack channel."""
        payload = {"channel": channel_id, "text": text}
        if thread_ts:
            payload["thread_ts"] = thread_ts

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SLACK_API_BASE}/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {bot_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            data = resp.json()
            if not data.get("ok"):
                logger.error("Failed to post Slack message: %s", data.get("error"))
            return data

    async def get_user_info(self, bot_token: str, user_id: str) -> dict:
        """Get Slack user info."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{SLACK_API_BASE}/users.info",
                headers={"Authorization": f"Bearer {bot_token}"},
                params={"user": user_id},
            )
            data = resp.json()
            if data.get("ok"):
                return data.get("user", {})
            return {}

    async def fetch_channel_history(
        self, bot_token: str, channel_id: str, oldest: str | None = None, limit: int = 100
    ) -> list[dict]:
        """Fetch recent messages from a channel."""
        params = {"channel": channel_id, "limit": limit}
        if oldest:
            params["oldest"] = oldest

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{SLACK_API_BASE}/conversations.history",
                headers={"Authorization": f"Bearer {bot_token}"},
                params=params,
            )
            data = resp.json()
            if not data.get("ok"):
                logger.error("Failed to fetch channel history: %s", data.get("error"))
                return []
            return data.get("messages", [])
