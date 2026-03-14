"""GitHub webhook integration — receive push, PR, issue, and review events."""
import hashlib
import hmac
import logging

from fastapi import APIRouter, HTTPException, Request, Response

from app.db.database import get_session

logger = logging.getLogger("collective_brain.github_webhooks")

router = APIRouter()


def _get_db():
    return next(get_session())


def _verify_signature(secret: str, body: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature (HMAC-SHA256)."""
    if not secret or not signature:
        return False
    if not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ─── Status ──────────────────────────────────────────────────


@router.get("/status")
async def github_status(request: Request):
    """Check whether GitHub webhook integration is configured."""
    from app.dependencies import get_current_user
    get_current_user(request)

    settings = request.app.state.settings
    configured = bool(settings.github_webhook_secret)
    return {
        "configured": configured,
        "webhook_url": f"/github/webhooks",
    }


@router.get("/setup")
async def github_setup(request: Request):
    """Return setup instructions for GitHub webhooks."""
    from app.dependencies import get_current_user
    get_current_user(request)

    settings = request.app.state.settings
    configured = bool(settings.github_webhook_secret)

    # Build the webhook URL based on the request
    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/github/webhooks"

    return {
        "configured": configured,
        "webhook_url": webhook_url,
        "instructions": [
            "1. Go to your GitHub repository → Settings → Webhooks → Add webhook",
            f"2. Set Payload URL to: {webhook_url}",
            "3. Set Content type to: application/json",
            "4. Set Secret to match your CB_GITHUB_WEBHOOK_SECRET environment variable",
            "5. Select events: Pushes, Pull requests, Issues, Issue comments, Pull request reviews",
            "6. Click 'Add webhook'",
        ],
        "required_env_vars": [
            "CB_GITHUB_WEBHOOK_SECRET — A secret string shared with GitHub for signature verification",
        ],
        "supported_events": [
            "push — Commits pushed to branches",
            "pull_request — PR opened, closed, merged, synchronized",
            "issues — Issues opened, closed, labeled",
            "issue_comment — Comments on issues and PRs",
            "pull_request_review — Code reviews submitted",
        ],
    }


# ─── Webhook Receiver ────────────────────────────────────────


@router.post("/webhooks")
async def github_webhook(request: Request):
    """Receive GitHub webhook events and process them."""
    settings = request.app.state.settings

    # Read raw body for signature verification
    body = await request.body()

    # Verify signature if secret is configured
    if settings.github_webhook_secret:
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not _verify_signature(settings.github_webhook_secret, body, signature):
            logger.warning("Invalid GitHub webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
    else:
        logger.warning("GitHub webhook secret not configured — accepting without verification")

    # Parse event type
    event_type = request.headers.get("X-GitHub-Event", "")
    delivery_id = request.headers.get("X-GitHub-Delivery", "")

    if event_type == "ping":
        logger.info("GitHub webhook ping received (delivery: %s)", delivery_id)
        return {"status": "pong", "delivery_id": delivery_id}

    # Parse payload
    try:
        import json
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Process in background via TaskQueue
    task_queue = request.app.state.task_queue
    embedder = request.app.state.embedding_service
    vs = request.app.state.vector_store

    async def _process():
        from app.services.github_event_processor import GitHubEventProcessor
        db = _get_db()
        try:
            processor = GitHubEventProcessor(db, embedder, vs)

            if event_type == "push":
                return processor.process_push(payload)
            elif event_type == "pull_request":
                return processor.process_pull_request(payload)
            elif event_type == "issues":
                return processor.process_issue(payload)
            elif event_type == "pull_request_review":
                return processor.process_review(payload)
            elif event_type == "issue_comment":
                return processor.process_issue_comment(payload)
            else:
                logger.info("Unhandled GitHub event type: %s", event_type)
                return {"status": "skipped", "reason": f"Event type '{event_type}' not supported"}
        except Exception as e:
            logger.error("Failed to process GitHub %s event: %s", event_type, e, exc_info=True)
            return {"status": "error", "error": str(e)}
        finally:
            db.close()

    task_id = await task_queue.submit(_process())

    logger.info("GitHub %s event queued (delivery: %s, task: %s)", event_type, delivery_id, task_id)

    # Return 200 immediately — GitHub requires response within 10 seconds
    return Response(status_code=200, content='{"status": "queued"}', media_type="application/json")


# ─── Recent Events ───────────────────────────────────────────


@router.get("/events")
async def github_recent_events(request: Request, limit: int = 20):
    """List recent GitHub-ingested artifacts."""
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        from app.models.artifact import ArtifactRecord
        artifacts = (
            db.query(ArtifactRecord)
            .filter(ArtifactRecord.source_type.in_(["github_push", "github_pr", "github_issue", "github_review", "github_comment"]))
            .order_by(ArtifactRecord.ingested_at.desc())
            .limit(limit)
            .all()
        )
        return {
            "events": [
                {
                    "id": a.id,
                    "type": a.source_type,
                    "title": a.title,
                    "source_path": a.source_path,
                    "chunk_count": a.chunk_count,
                    "ingested_at": a.ingested_at.isoformat() if a.ingested_at else None,
                    "member_ids": a.member_ids or [],
                }
                for a in artifacts
            ],
            "total": len(artifacts),
        }
    finally:
        db.close()
