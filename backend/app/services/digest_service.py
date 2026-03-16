"""Weekly Slack Digest Bot — compiles and sends team knowledge digests."""
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.contribution import ContributionRecord
from app.models.member import MemberRecord
from app.models.artifact import ArtifactRecord
from app.models.slack_integration import SlackWorkspace
from app.services.memory_graph import MemoryGraph

logger = logging.getLogger("collective_brain.digest")

SLACK_API_BASE = "https://slack.com/api"


def generate_weekly_digest(db: Session, room_id: str | None = None) -> dict:
    """Compile a structured weekly digest from the last 7 days of activity.

    Returns a DigestData dict with all metrics, highlights, and risks.
    """
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    # ── Recent contributions (last 7 days) ────────────────────
    contrib_query = (
        db.query(ContributionRecord)
        .filter(ContributionRecord.timestamp >= week_ago)
    )
    if room_id:
        contrib_query = contrib_query.filter(ContributionRecord.room_id == room_id)
    recent_contribs = contrib_query.order_by(ContributionRecord.timestamp.desc()).all()

    # ── Count new members this week ───────────────────────────
    new_members_query = (
        db.query(MemberRecord)
        .filter(MemberRecord.first_seen >= week_ago)
    )
    new_members = new_members_query.all()

    # ── Count new artifacts this week ─────────────────────────
    new_artifacts_query = db.query(ArtifactRecord)
    if room_id:
        new_artifacts_query = new_artifacts_query.filter(ArtifactRecord.room_id == room_id)
    # ArtifactRecord may not have created_at; count artifacts that have contributions this week
    artifact_ids_this_week = list({
        c.artifact_id for c in recent_contribs if c.artifact_id
    })

    # ── Topics this week ──────────────────────────────────────
    topic_counts: dict[str, int] = defaultdict(int)
    contributor_set: set[str] = set()
    contribution_type_counts: dict[str, int] = defaultdict(int)

    for c in recent_contribs:
        if c.member_id:
            contributor_set.add(c.member_id)
        if c.contribution_type:
            contribution_type_counts[c.contribution_type] += 1
        for topic in c.topics or []:
            topic_counts[topic] += 1

    top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # ── Graph stats ───────────────────────────────────────────
    graph = MemoryGraph(db, room_id=room_id)
    graph_stats = graph.get_graph_stats()

    # ── Bus factor risks (topics with only 1 expert) ──────────
    expertise_gaps = graph.get_expertise_gaps()
    bus_factor_risks = [
        r for r in expertise_gaps.get("bus_factor_risks", [])
        if r.get("severity") == "high"
    ][:10]

    # ── Top contributors this week ────────────────────────────
    member_contrib_counts: dict[str, int] = defaultdict(int)
    for c in recent_contribs:
        if c.member_id:
            member_contrib_counts[c.member_id] += 1

    top_contributors_raw = sorted(
        member_contrib_counts.items(), key=lambda x: x[1], reverse=True
    )[:5]

    # Resolve member names
    top_contributor_ids = [mid for mid, _ in top_contributors_raw]
    members_by_id = {}
    if top_contributor_ids:
        members = db.query(MemberRecord).filter(MemberRecord.id.in_(top_contributor_ids)).all()
        members_by_id = {m.id: m.name for m in members}

    top_contributors = [
        {"member_id": mid, "name": members_by_id.get(mid, mid), "count": count}
        for mid, count in top_contributors_raw
    ]

    digest_data = {
        "period_start": week_ago.isoformat(),
        "period_end": now.isoformat(),
        "total_contributions": len(recent_contribs),
        "active_contributors": len(contributor_set),
        "new_members": [{"id": m.id, "name": m.name} for m in new_members],
        "new_members_count": len(new_members),
        "new_artifacts_count": len(artifact_ids_this_week),
        "top_topics": [{"topic": t, "count": c} for t, c in top_topics],
        "top_contributors": top_contributors,
        "contribution_types": dict(contribution_type_counts),
        "graph_stats": graph_stats,
        "bus_factor_risks": [
            {
                "topic": r.get("topic", ""),
                "sole_expert": r.get("sole_expert", {}).get("name", "Unknown"),
            }
            for r in bus_factor_risks
        ],
        "bus_factor_risk_count": len(bus_factor_risks),
    }

    return digest_data


def format_slack_blocks(digest_data: dict) -> list[dict]:
    """Format digest data as Slack Block Kit JSON blocks."""
    period_start = digest_data["period_start"][:10]
    period_end = digest_data["period_end"][:10]

    blocks: list[dict] = []

    # ── Header ────────────────────────────────────────────────
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"Weekly Knowledge Digest: {period_start} to {period_end}",
            "emoji": True,
        },
    })

    # ── Overview section ──────────────────────────────────────
    overview_lines = [
        f"*Contributions:* {digest_data['total_contributions']}",
        f"*Active contributors:* {digest_data['active_contributors']}",
        f"*New members:* {digest_data['new_members_count']}",
        f"*New artifacts:* {digest_data['new_artifacts_count']}",
    ]
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "\n".join(overview_lines),
        },
    })

    blocks.append({"type": "divider"})

    # ── Top Contributors ──────────────────────────────────────
    if digest_data["top_contributors"]:
        contrib_lines = []
        for i, tc in enumerate(digest_data["top_contributors"], 1):
            medal = ["", "", ""][i - 1] if i <= 3 else f"{i}."
            contrib_lines.append(f"{medal} *{tc['name']}* — {tc['count']} contributions")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Top Contributors*\n" + "\n".join(contrib_lines),
            },
        })

        blocks.append({"type": "divider"})

    # ── Trending Topics ───────────────────────────────────────
    if digest_data["top_topics"]:
        topic_lines = [
            f"  {t['topic']} ({t['count']} mentions)"
            for t in digest_data["top_topics"][:7]
        ]
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Trending Topics*\n" + "\n".join(topic_lines),
            },
        })

        blocks.append({"type": "divider"})

    # ── Bus Factor Risks ──────────────────────────────────────
    if digest_data["bus_factor_risks"]:
        risk_lines = [
            f"  *{r['topic']}* — only expert: {r['sole_expert']}"
            for r in digest_data["bus_factor_risks"][:5]
        ]
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Bus Factor Risks* ({digest_data['bus_factor_risk_count']} topics at risk)\n"
                    + "\n".join(risk_lines)
                ),
            },
        })

        blocks.append({"type": "divider"})

    # ── Graph Stats ───────────────────────────────────────────
    gs = digest_data.get("graph_stats", {})
    if gs:
        graph_lines = [
            f"*Knowledge Graph:* {gs.get('total_nodes', 0)} nodes, "
            f"{gs.get('total_edges', 0)} edges",
            f"*Members:* {gs.get('members', 0)} | "
            f"*Topics:* {gs.get('topics', 0)} | "
            f"*Artifacts:* {gs.get('artifacts', 0)}",
            f"*Communities:* {gs.get('communities', 0)} | "
            f"*Density:* {gs.get('density', 0):.4f}",
        ]
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(graph_lines),
            },
        })

    # ── New Members ───────────────────────────────────────────
    if digest_data["new_members"]:
        member_names = ", ".join(m["name"] for m in digest_data["new_members"][:10])
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"New team members this week: {member_names}",
                }
            ],
        })

    # ── Footer ────────────────────────────────────────────────
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Generated by Collective Brain on {digest_data['period_end'][:10]}",
            }
        ],
    })

    return blocks


def format_text_digest(digest_data: dict) -> str:
    """Format digest data as plain text for preview."""
    period_start = digest_data["period_start"][:10]
    period_end = digest_data["period_end"][:10]

    lines = [
        f"=== Weekly Knowledge Digest: {period_start} to {period_end} ===",
        "",
        f"Contributions: {digest_data['total_contributions']}",
        f"Active contributors: {digest_data['active_contributors']}",
        f"New members: {digest_data['new_members_count']}",
        f"New artifacts: {digest_data['new_artifacts_count']}",
        "",
    ]

    if digest_data["top_contributors"]:
        lines.append("-- Top Contributors --")
        for i, tc in enumerate(digest_data["top_contributors"], 1):
            lines.append(f"  {i}. {tc['name']} — {tc['count']} contributions")
        lines.append("")

    if digest_data["top_topics"]:
        lines.append("-- Trending Topics --")
        for t in digest_data["top_topics"][:7]:
            lines.append(f"  - {t['topic']} ({t['count']} mentions)")
        lines.append("")

    if digest_data["bus_factor_risks"]:
        lines.append(f"-- Bus Factor Risks ({digest_data['bus_factor_risk_count']} topics) --")
        for r in digest_data["bus_factor_risks"][:5]:
            lines.append(f"  ! {r['topic']} — only expert: {r['sole_expert']}")
        lines.append("")

    gs = digest_data.get("graph_stats", {})
    if gs:
        lines.append("-- Knowledge Graph --")
        lines.append(f"  Nodes: {gs.get('total_nodes', 0)}, Edges: {gs.get('total_edges', 0)}")
        lines.append(
            f"  Members: {gs.get('members', 0)}, "
            f"Topics: {gs.get('topics', 0)}, "
            f"Artifacts: {gs.get('artifacts', 0)}"
        )
        lines.append(
            f"  Communities: {gs.get('communities', 0)}, "
            f"Density: {gs.get('density', 0):.4f}"
        )
        lines.append("")

    if digest_data["new_members"]:
        member_names = ", ".join(m["name"] for m in digest_data["new_members"][:10])
        lines.append(f"New team members: {member_names}")
        lines.append("")

    lines.append(f"Generated by Collective Brain on {period_end}")
    return "\n".join(lines)


async def send_digest_to_slack(
    db: Session,
    workspace_id: str,
    channel_id: str,
    room_id: str | None = None,
) -> dict:
    """Compile and post a weekly digest to a Slack channel.

    Uses the workspace's bot_token from the DB to authenticate with Slack.
    Returns the Slack API response dict.
    """
    # Look up workspace for bot_token
    workspace = db.query(SlackWorkspace).filter(SlackWorkspace.id == workspace_id).first()
    if not workspace or not workspace.is_active:
        raise ValueError(f"Workspace {workspace_id} not found or inactive")
    if not workspace.bot_token:
        raise ValueError(f"Workspace {workspace_id} has no bot token")

    # Generate digest
    digest_data = generate_weekly_digest(db, room_id=room_id)

    # Format as Slack blocks
    blocks = format_slack_blocks(digest_data)

    # Build fallback text (Slack requires a text field alongside blocks)
    fallback_text = (
        f"Weekly Knowledge Digest: {digest_data['period_start'][:10]} "
        f"to {digest_data['period_end'][:10]} — "
        f"{digest_data['total_contributions']} contributions from "
        f"{digest_data['active_contributors']} contributors"
    )

    # Post to Slack
    payload = {
        "channel": channel_id,
        "text": fallback_text,
        "blocks": blocks,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SLACK_API_BASE}/chat.postMessage",
            headers={
                "Authorization": f"Bearer {workspace.bot_token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        data = resp.json()
        if not data.get("ok"):
            logger.error("Failed to post digest to Slack: %s", data.get("error"))
            raise ValueError(f"Slack API error: {data.get('error', 'unknown')}")

        logger.info(
            "Digest posted to workspace=%s channel=%s (%d contributions)",
            workspace_id,
            channel_id,
            digest_data["total_contributions"],
        )

        # Update last_sent_at for any matching digest config
        try:
            from app.db.database import update_digest_last_sent
            # Find config for this workspace + channel
            row = db.execute(
                text(
                    "SELECT id FROM slack_digest_config "
                    "WHERE workspace_id = :wid AND channel_id = :cid LIMIT 1"
                ),
                {"wid": workspace_id, "cid": channel_id},
            ).fetchone()
            if row:
                update_digest_last_sent(db, row[0])
        except Exception as e:
            logger.warning("Failed to update digest last_sent_at: %s", e)

        return {
            "ok": True,
            "channel": channel_id,
            "ts": data.get("ts"),
            "digest_data": digest_data,
        }
