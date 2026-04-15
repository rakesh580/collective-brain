"""Knowledge Decay & Freshness analysis for artifacts.

Computes staleness scores for artifacts based on age and related activity,
classifies them as fresh/aging/stale, and generates freshness reports.
"""

import logging
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.artifact import ArtifactRecord
from app.models.contribution import ContributionRecord
from app.models.member import MemberRecord

logger = logging.getLogger("collective_brain.freshness")


def compute_artifact_freshness(db: Session) -> list[dict]:
    """Compute freshness info for every artifact in the database.

    For each artifact:
      1. Get ingested_at timestamp
      2. Calculate days since ingestion
      3. Count contributions in similar topics since ingestion
      4. Compute staleness score: days_since_ingestion * (1 + related_changes * 0.1)
      5. Classify: fresh / aging / stale
      6. Return list with freshness metadata
    """
    now = datetime.now(UTC)
    artifacts = db.query(ArtifactRecord).all()
    contributions = db.query(ContributionRecord).all()

    # Build a map: artifact_id -> list of topics
    artifact_topics: dict[str, set[str]] = defaultdict(set)
    for c in contributions:
        if c.artifact_id and c.topics:
            for topic in c.topics:
                artifact_topics[c.artifact_id].add(topic.lower().strip())

    # Build a map: topic -> list of contributions (with timestamps)
    topic_contributions: dict[str, list[ContributionRecord]] = defaultdict(list)
    for c in contributions:
        if c.topics:
            for topic in c.topics:
                topic_contributions[topic.lower().strip()].append(c)

    # Build member name lookup
    members = db.query(MemberRecord).all()
    member_name_map: dict[str, str] = {m.id: m.name for m in members}

    results: list[dict] = []
    for artifact in artifacts:
        ingested_at = artifact.ingested_at or now
        days_since = max(0, (now - ingested_at).days)

        # Count contributions in similar topics since this artifact was ingested
        artifact_topic_set = artifact_topics.get(artifact.id, set())
        related_changes = 0
        if artifact_topic_set:
            seen_contrib_ids: set[str] = set()
            for topic in artifact_topic_set:
                for c in topic_contributions.get(topic, []):
                    if (
                        c.id not in seen_contrib_ids
                        and c.artifact_id != artifact.id
                        and c.timestamp
                        and c.timestamp > ingested_at
                    ):
                        related_changes += 1
                        seen_contrib_ids.add(c.id)

        # Staleness score
        staleness_score = round(days_since * (1 + related_changes * 0.1), 1)

        # Classification
        if days_since < 30 or staleness_score < 30:
            status = "fresh"
        elif days_since <= 90 or staleness_score <= 90:
            status = "aging"
        else:
            status = "stale"

        # Responsible members: those linked to this artifact
        responsible_member_ids = artifact.member_ids or []
        responsible_members = [
            member_name_map.get(mid, mid) for mid in responsible_member_ids
        ]

        results.append({
            "artifact_id": artifact.id,
            "title": artifact.title or artifact.source_path or artifact.id,
            "source_type": artifact.source_type or "unknown",
            "ingested_at": ingested_at.isoformat(),
            "days_old": days_since,
            "staleness_score": staleness_score,
            "status": status,
            "related_changes": related_changes,
            "responsible_members": responsible_members,
        })

    # Sort by staleness_score descending (most stale first)
    results.sort(key=lambda x: x["staleness_score"], reverse=True)
    return results


def get_stale_artifacts(db: Session, threshold_days: int = 90) -> list[dict]:
    """Return only artifacts classified as stale."""
    all_freshness = compute_artifact_freshness(db)
    return [a for a in all_freshness if a["status"] == "stale"]


def get_freshness_report(db: Session) -> dict:
    """Generate a full freshness report with summary, alerts, and worst offenders.

    Returns:
        summary: counts per category (fresh/aging/stale/total)
        alerts: all artifacts with freshness info
        worst_offenders: top 10 most stale artifacts
    """
    all_freshness = compute_artifact_freshness(db)

    fresh_count = sum(1 for a in all_freshness if a["status"] == "fresh")
    aging_count = sum(1 for a in all_freshness if a["status"] == "aging")
    stale_count = sum(1 for a in all_freshness if a["status"] == "stale")

    return {
        "summary": {
            "fresh": fresh_count,
            "aging": aging_count,
            "stale": stale_count,
            "total": len(all_freshness),
        },
        "alerts": all_freshness,
        "worst_offenders": all_freshness[:10],
    }
