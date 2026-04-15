"""Slack bot integration endpoints — OAuth, Events API, slash commands, digest."""

import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.db.database import create_session
from app.models.slack_integration import SlackChannelSync, SlackWorkspace

logger = logging.getLogger("collective_brain.slack_router")

router = APIRouter()


def _get_db():
    return create_session()


# ─── Status Check ─────────────────────────────────────────────


@router.get("/status")
async def slack_status(request: Request):
    """Check whether Slack integration is configured on the server."""
    from app.dependencies import get_current_user

    get_current_user(request)

    settings = request.app.state.settings
    configured = bool(settings.slack_client_id and settings.slack_client_secret)
    return {
        "configured": configured,
        "has_signing_secret": bool(settings.slack_signing_secret),
    }


# ─── OAuth Flow ───────────────────────────────────────────────


@router.get("/install")
async def slack_install(request: Request):
    """Start Slack app installation — redirects to Slack OAuth."""
    from app.dependencies import get_current_user

    get_current_user(request)

    settings = request.app.state.settings
    if not settings.slack_client_id:
        raise HTTPException(status_code=400, detail="Slack integration is not configured")

    from app.services.slack_service import SlackService

    slack = SlackService(settings)

    # Build redirect URI based on request origin
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/slack/oauth/callback"

    # Generate state token for CSRF protection
    import secrets
    import time as _time

    state = secrets.token_urlsafe(32)

    # Store state with expiry — use Redis if available, else in-memory with TTL
    redis = getattr(request.app.state, "redis", None)
    if redis and redis.is_connected:
        await redis.cache_set(f"slack_oauth_state:{state}", True, ttl_seconds=600)
    else:
        _states = getattr(request.app.state, "_slack_oauth_states", {})
        # Clean up expired states (older than 10 minutes)
        now = _time.time()
        request.app.state._slack_oauth_states = {k: v for k, v in _states.items() if now - v < 600}
        request.app.state._slack_oauth_states[state] = now

    url = slack.get_install_url(redirect_uri, state)
    return {"install_url": url}


@router.get("/oauth/callback")
async def slack_oauth_callback(request: Request, code: str, state: str):
    """Handle Slack OAuth callback after installation."""
    settings = request.app.state.settings
    if not settings.slack_client_id:
        raise HTTPException(status_code=400, detail="Slack integration is not configured")

    # Verify state (CSRF protection) — check Redis first, then in-memory
    redis = getattr(request.app.state, "redis", None)
    state_valid = False
    if redis and redis.is_connected:
        cached = await redis.cache_get(f"slack_oauth_state:{state}")
        if cached:
            state_valid = True
            await redis.cache_delete(f"slack_oauth_state:{state}")
    else:
        oauth_states = getattr(request.app.state, "_slack_oauth_states", {})
        if state in oauth_states:
            state_valid = True
            del oauth_states[state]
    if not state_valid:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    from app.services.slack_service import SlackService

    slack = SlackService(settings)

    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/slack/oauth/callback"

    try:
        oauth_data = await slack.exchange_code(code, redirect_uri)
    except Exception as e:
        logger.error("Slack OAuth exchange failed: %s", e)
        raise HTTPException(status_code=400, detail=f"OAuth failed: {e}")

    db = _get_db()
    try:
        # Save workspace (no user context for callback — use installer info from OAuth)
        workspace = await slack.save_workspace(db, oauth_data, installed_by_user_id="")
        logger.info("Slack workspace connected: %s (%s)", workspace.team_name, workspace.id)

        # Redirect to frontend settings page
        return RedirectResponse(url="/?slack=connected")
    finally:
        db.close()


# ─── Workspace Management ─────────────────────────────────────


@router.get("/workspaces")
async def list_workspaces(request: Request):
    """List connected Slack workspaces."""
    from app.dependencies import get_current_user

    get_current_user(request)

    db = _get_db()
    try:
        workspaces = db.query(SlackWorkspace).filter(SlackWorkspace.is_active == True).all()  # noqa: E712
        return {
            "workspaces": [
                {
                    "id": w.id,
                    "team_name": w.team_name,
                    "installed_at": w.installed_at.isoformat() if w.installed_at else None,
                    "is_active": w.is_active,
                }
                for w in workspaces
            ]
        }
    finally:
        db.close()


@router.delete("/workspaces/{workspace_id}")
async def disconnect_workspace(workspace_id: str, request: Request):
    """Disconnect a Slack workspace."""
    from app.dependencies import get_current_user

    get_current_user(request)

    db = _get_db()
    try:
        workspace = db.query(SlackWorkspace).filter(SlackWorkspace.id == workspace_id).first()
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
        workspace.is_active = False
        # Deactivate all channel syncs
        db.query(SlackChannelSync).filter(SlackChannelSync.workspace_id == workspace_id).update({"is_active": False})
        db.commit()
        return {"status": "disconnected"}
    finally:
        db.close()


# ─── Channel Sync Management ──────────────────────────────────


@router.get("/workspaces/{workspace_id}/channels")
async def list_slack_channels(workspace_id: str, request: Request):
    """List available Slack channels for syncing."""
    from app.dependencies import get_current_user

    get_current_user(request)

    db = _get_db()
    try:
        workspace = db.query(SlackWorkspace).filter(SlackWorkspace.id == workspace_id).first()
        if not workspace or not workspace.is_active:
            raise HTTPException(status_code=404, detail="Workspace not found")

        settings = request.app.state.settings
        from app.services.slack_service import SlackService

        slack = SlackService(settings)
        channels = await slack.list_channels(workspace.bot_token)

        # Mark which channels are already synced
        synced = {
            s.slack_channel_id: s
            for s in db.query(SlackChannelSync).filter(SlackChannelSync.workspace_id == workspace_id).all()
        }

        return {
            "channels": [
                {
                    "id": ch["id"],
                    "name": ch.get("name", ""),
                    "is_private": ch.get("is_private", False),
                    "member_count": ch.get("num_members", 0),
                    "is_synced": ch["id"] in synced,
                    "sync_id": synced[ch["id"]].id if ch["id"] in synced else None,
                    "sync_mode": synced[ch["id"]].sync_mode if ch["id"] in synced else None,
                }
                for ch in channels
            ]
        }
    finally:
        db.close()


@router.post("/workspaces/{workspace_id}/channels/{channel_id}/sync")
async def sync_channel(
    workspace_id: str,
    channel_id: str,
    request: Request,
    room_id: str | None = None,
    sync_mode: str = "ingest",
):
    """Start syncing a Slack channel to Collective Brain."""
    from app.dependencies import get_current_user

    get_current_user(request)

    db = _get_db()
    try:
        workspace = db.query(SlackWorkspace).filter(SlackWorkspace.id == workspace_id).first()
        if not workspace or not workspace.is_active:
            raise HTTPException(status_code=404, detail="Workspace not found")

        # Check if already synced
        existing = (
            db.query(SlackChannelSync)
            .filter(
                SlackChannelSync.workspace_id == workspace_id,
                SlackChannelSync.slack_channel_id == channel_id,
            )
            .first()
        )
        if existing:
            existing.is_active = True
            existing.sync_mode = sync_mode
            existing.room_id = room_id
            db.commit()
            return {"status": "updated", "sync_id": existing.id}

        # Get channel name
        settings = request.app.state.settings
        from app.services.slack_service import SlackService

        slack = SlackService(settings)
        channels = await slack.list_channels(workspace.bot_token)
        channel_name = next(
            (ch.get("name", "") for ch in channels if ch["id"] == channel_id),
            channel_id,
        )

        sync = SlackChannelSync(
            id=str(uuid4()),
            workspace_id=workspace_id,
            slack_channel_id=channel_id,
            slack_channel_name=channel_name,
            room_id=room_id,
            sync_mode=sync_mode,
        )
        db.add(sync)
        db.commit()

        return {"status": "syncing", "sync_id": sync.id, "channel_name": channel_name}
    finally:
        db.close()


@router.delete("/syncs/{sync_id}")
async def stop_sync(sync_id: str, request: Request):
    """Stop syncing a Slack channel."""
    from app.dependencies import get_current_user

    get_current_user(request)

    db = _get_db()
    try:
        sync = db.query(SlackChannelSync).filter(SlackChannelSync.id == sync_id).first()
        if not sync:
            raise HTTPException(status_code=404, detail="Sync not found")
        sync.is_active = False
        db.commit()
        return {"status": "stopped"}
    finally:
        db.close()


@router.post("/syncs/{sync_id}/backfill")
async def backfill_sync(sync_id: str, request: Request, limit: int = 200):
    """Backfill historical messages from a synced Slack channel."""
    from app.dependencies import get_current_user

    get_current_user(request)

    db = _get_db()
    try:
        sync = db.query(SlackChannelSync).filter(SlackChannelSync.id == sync_id).first()
        if not sync:
            raise HTTPException(status_code=404, detail="Sync not found")

        settings = request.app.state.settings
        from app.services.slack_event_processor import SlackEventProcessor
        from app.services.slack_service import SlackService

        slack = SlackService(settings)
        processor = SlackEventProcessor(
            db=db,
            slack_service=slack,
            embedder=request.app.state.embedding_service,
            vector_store=request.app.state.vector_store,
        )

        count = await processor.backfill_channel(sync.workspace_id, sync.slack_channel_id, limit=limit)
        return {"status": "backfilled", "messages_ingested": count}
    finally:
        db.close()


# ─── Slack Events API ─────────────────────────────────────────


@router.post("/events")
async def slack_events(request: Request):
    """Handle Slack Events API — URL verification and message events."""
    body = await request.body()
    import json

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # URL verification challenge (Slack sends this when setting up Events API)
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge", "")}

    # Verify request signature
    settings = request.app.state.settings
    if settings.slack_signing_secret:
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")
        from app.services.slack_service import SlackService

        slack = SlackService(settings)
        if not slack.verify_signature(timestamp, body, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Handle event callbacks
    if payload.get("type") == "event_callback":
        event = payload.get("event", {})
        team_id = payload.get("team_id", "")
        event_type = event.get("type", "")

        db = _get_db()
        try:
            if event_type == "message" and not event.get("subtype"):
                from app.services.slack_event_processor import SlackEventProcessor
                from app.services.slack_service import SlackService

                slack_svc = SlackService(settings)
                processor = SlackEventProcessor(
                    db=db,
                    slack_service=slack_svc,
                    embedder=request.app.state.embedding_service,
                    vector_store=request.app.state.vector_store,
                )
                await processor.process_message(event, team_id)

            elif event_type == "app_mention":
                from app.services.rag_pipeline import RAGPipeline
                from app.services.slack_event_processor import SlackEventProcessor
                from app.services.slack_service import SlackService

                slack_svc = SlackService(settings)
                processor = SlackEventProcessor(
                    db=db,
                    slack_service=slack_svc,
                    embedder=request.app.state.embedding_service,
                    vector_store=request.app.state.vector_store,
                )

                result = await processor.process_app_mention(event, team_id)
                if result:
                    clean_text, room_id, bot_token, channel_id, thread_ts = result

                    # Run RAG pipeline
                    pipeline = RAGPipeline(
                        llm=request.app.state.llm_service,
                        embedder=request.app.state.embedding_service,
                        vector_store=request.app.state.vector_store,
                        db=db,
                    )
                    answer = await pipeline.answer(
                        question=clean_text,
                        room_id=room_id,
                    )

                    # Reply in Slack thread
                    await slack_svc.post_message(bot_token, channel_id, answer.answer, thread_ts=thread_ts)
        finally:
            db.close()

    # Slack expects a 200 response within 3 seconds
    return Response(status_code=200)


# ─── Slash Commands ───────────────────────────────────────────


@router.post("/commands")
async def slack_commands(request: Request):
    """Handle Slack slash commands (e.g., /brain ask <question>)."""
    body = await request.body()

    # Verify signature
    settings = request.app.state.settings
    if settings.slack_signing_secret:
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")
        from app.services.slack_service import SlackService

        slack = SlackService(settings)
        if not slack.verify_signature(timestamp, body, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    form = await request.form()
    form.get("command", "")
    text = form.get("text", "").strip()
    channel_id = form.get("channel_id", "")
    team_id = form.get("team_id", "")

    if not text:
        return {
            "response_type": "ephemeral",
            "text": (
                "Usage:\n"
                "  `/brain ask <question>` — Ask the AI about your team\n"
                "  `/brain who <topic>` — Find the best person for a topic\n"
                "  `/brain summary` — Get a weekly summary"
            ),
        }

    # Parse sub-command
    parts = text.split(maxsplit=1)
    sub_cmd = parts[0].lower()
    query_text = parts[1] if len(parts) > 1 else ""

    if sub_cmd == "ask" and query_text:
        question = query_text
    elif sub_cmd == "who" and query_text:
        question = f"Who is the best person to handle {query_text}?"
    elif sub_cmd == "summary":
        question = "Give me a weekly summary of team activity"
    else:
        question = text  # Use full text as question

    # Find room_id for this channel
    db = _get_db()
    try:
        sync = (
            db.query(SlackChannelSync)
            .filter(
                SlackChannelSync.workspace_id == team_id,
                SlackChannelSync.slack_channel_id == channel_id,
                SlackChannelSync.is_active == True,  # noqa: E712
            )
            .first()
        )
        room_id = sync.room_id if sync else None

        # Run RAG pipeline
        from app.services.rag_pipeline import RAGPipeline

        pipeline = RAGPipeline(
            llm=request.app.state.llm_service,
            embedder=request.app.state.embedding_service,
            vector_store=request.app.state.vector_store,
            db=db,
        )
        answer = await pipeline.answer(question=question, room_id=room_id)

        # Format sources
        source_text = ""
        if answer.sources:
            source_refs = list({s.source_ref for s in answer.sources[:3] if s.source_ref})
            if source_refs:
                source_text = "\n\n_Sources: " + ", ".join(source_refs) + "_"

        return {
            "response_type": "in_channel",
            "text": f"{answer.answer}{source_text}",
        }
    except Exception as e:
        logger.error("Slash command failed: %s", e, exc_info=True)
        return {
            "response_type": "ephemeral",
            "text": "Sorry, I encountered an error processing your request. Please try again.",
        }
    finally:
        db.close()


# ─── Pydantic Models for Digest Endpoints ─────────────────────


class DigestSendRequest(BaseModel):
    workspace_id: str
    channel_id: str


class DigestConfigureRequest(BaseModel):
    workspace_id: str
    channel_id: str
    channel_name: str = ""
    schedule_day: int = 0  # 0=Monday
    schedule_hour: int = 9
    enabled: bool = True


# ─── Weekly Digest Endpoints ──────────────────────────────────


@router.post("/digest/send")
async def digest_send(body: DigestSendRequest, request: Request):
    """Manually trigger a weekly digest send to a specified Slack channel."""
    from app.dependencies import get_current_user

    get_current_user(request)

    from app.services.digest_service import send_digest_to_slack

    db = _get_db()
    try:
        result = await send_digest_to_slack(
            db=db,
            workspace_id=body.workspace_id,
            channel_id=body.channel_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Digest send failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send digest")
    finally:
        db.close()


@router.get("/digest/preview")
async def digest_preview(request: Request):
    """Preview the weekly digest content as JSON and plain text (does not send to Slack)."""
    from app.dependencies import get_current_user

    get_current_user(request)

    from app.services.digest_service import (
        format_slack_blocks,
        format_text_digest,
        generate_weekly_digest,
    )

    db = _get_db()
    try:
        digest_data = generate_weekly_digest(db)
        blocks = format_slack_blocks(digest_data)
        text_version = format_text_digest(digest_data)

        # Build a frontend-compatible DigestPreview object
        gs = digest_data.get("graph_stats", {})
        digest_preview = {
            "period_start": digest_data.get("period_start", ""),
            "period_end": digest_data.get("period_end", ""),
            "summary": text_version.split("\n\n")[0] if text_version else "",
            "highlights": [t["topic"] + f" ({t['count']} mentions)" for t in digest_data.get("top_topics", [])[:5]],
            "metrics": {
                "total_members": gs.get("members", 0),
                "total_artifacts": gs.get("artifacts", 0),
                "new_contributions": digest_data.get("total_contributions", 0),
                "active_members": digest_data.get("active_contributors", 0),
                "bus_factor_risks": digest_data.get("bus_factor_risk_count", 0),
            },
            "top_contributors": [
                {"name": tc.get("name", ""), "contributions": tc.get("count", 0)}
                for tc in digest_data.get("top_contributors", [])
            ],
            "trending_topics": [t["topic"] for t in digest_data.get("top_topics", [])[:10]],
        }

        return {
            "digest": digest_preview,
            "digest_data": digest_data,
            "slack_blocks": blocks,
            "text_preview": text_version,
        }
    except Exception as e:
        logger.error("Digest preview failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate digest preview")
    finally:
        db.close()


@router.post("/digest/configure")
async def digest_configure(body: DigestConfigureRequest, request: Request):
    """Save or update digest schedule configuration for a workspace + channel."""
    from app.dependencies import get_current_user

    get_current_user(request)

    from app.db.database import save_digest_config

    db = _get_db()
    try:
        # Verify workspace exists
        workspace = db.query(SlackWorkspace).filter(SlackWorkspace.id == body.workspace_id).first()
        if not workspace or not workspace.is_active:
            raise HTTPException(status_code=404, detail="Workspace not found or inactive")

        config = save_digest_config(
            db=db,
            workspace_id=body.workspace_id,
            channel_id=body.channel_id,
            channel_name=body.channel_name,
            schedule_day=body.schedule_day,
            schedule_hour=body.schedule_hour,
            enabled=body.enabled,
        )
        return {"status": "saved", "config": config}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Digest configure failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save digest configuration")
    finally:
        db.close()


@router.get("/digest/config")
async def digest_get_config(request: Request, workspace_id: str = ""):
    """Get current digest configuration(s) for a workspace.

    If workspace_id is omitted, returns the config for the first active workspace.
    Also returns a single ``config`` key (first result or null) for frontend compatibility.
    """
    from app.dependencies import get_current_user

    get_current_user(request)

    from app.db.database import get_digest_config

    db = _get_db()
    try:
        # If no workspace_id provided, pick the first active workspace
        if not workspace_id:
            first_ws = (
                db.query(SlackWorkspace)
                .filter(SlackWorkspace.is_active == True)  # noqa: E712
                .first()
            )
            if first_ws:
                workspace_id = first_ws.id
            else:
                return {"configs": [], "config": None}

        configs = get_digest_config(db, workspace_id)
        return {"configs": configs, "config": configs[0] if configs else None}
    finally:
        db.close()
