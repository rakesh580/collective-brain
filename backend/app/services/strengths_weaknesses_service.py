"""Nightly strengths/weaknesses analyzer.

Scans ``ContributionRecord`` rows and populates:

- ``MemberRecord.strengths`` — top topics each member dominated in the last 30d
- ``MemberRecord.weaknesses`` — topics a member previously owned (60-30d ago)
  that went silent in the last 30d (stale expertise / knowledge going cold)
- ``OrganizationRecord.strengths_weaknesses_json`` — org-wide aggregate so the
  Friday digest can surface "team strengths / weaknesses this quarter"

Idempotent by design: same inputs → same output. Runs nightly at 03:30 UTC
(after ``contribution_rollup`` at 02:30, before ``pattern_detection`` at
04:00).
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.contribution import ContributionRecord
from app.models.member import MemberRecord
from app.models.organization import OrganizationRecord

logger = logging.getLogger("collective_brain.strengths_weaknesses")

# Lookback windows (days). Current = last 30d; prior = 60-30d ago.
CURRENT_WINDOW_DAYS = 30
PRIOR_WINDOW_DAYS = 60
# Minimum contributions in a topic to call it a strength or weakness.
MIN_TOPIC_COUNT = 3
# How many chips we surface per member and per org.
MAX_MEMBER_STRENGTHS = 3
MAX_MEMBER_WEAKNESSES = 3
MAX_ORG_ITEMS = 5
MAX_ORG_TOP_MEMBERS = 5


def _topic_counts(
    rows: list[ContributionRecord],
) -> Counter[str]:
    counter: Counter[str] = Counter()
    for r in rows:
        for t in r.topics or []:
            if t:
                counter[str(t)] += 1
    return counter


def _member_strengths_and_weaknesses(
    current_rows: list[ContributionRecord],
    prior_rows: list[ContributionRecord],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Compute (strengths, weaknesses) for a single member."""
    current = _topic_counts(current_rows)
    prior = _topic_counts(prior_rows)

    strengths = [
        {"topic": topic, "count": count}
        for topic, count in current.most_common()
        if count >= MIN_TOPIC_COUNT
    ][:MAX_MEMBER_STRENGTHS]

    weaknesses = [
        {"topic": topic, "prior_count": prior_count, "current_count": 0}
        for topic, prior_count in prior.most_common()
        if prior_count >= MIN_TOPIC_COUNT and current.get(topic, 0) == 0
    ][:MAX_MEMBER_WEAKNESSES]

    return strengths, weaknesses


def _org_summary(
    *,
    org_id: str | None,
    member_ids: list[str],
    current_rows: list[ContributionRecord],
    prior_rows: list[ContributionRecord],
    member_names_by_id: dict[str, str],
    computed_at: datetime,
) -> dict[str, Any]:
    """Build the org-level strengths_weaknesses_json payload."""
    current_topic_counts = _topic_counts(current_rows)
    prior_topic_counts = _topic_counts(prior_rows)

    # Active contributors per topic (for bus-factor detection).
    topic_members: dict[str, set[str]] = defaultdict(set)
    for r in current_rows:
        if not r.member_id:
            continue
        for t in r.topics or []:
            if t:
                topic_members[str(t)].add(r.member_id)

    strengths = [
        {
            "topic": topic,
            "count": count,
            "contributors": len(topic_members.get(topic, set())),
        }
        for topic, count in current_topic_counts.most_common(MAX_ORG_ITEMS)
        if count >= MIN_TOPIC_COUNT
    ]

    weaknesses = [
        {
            "topic": topic,
            "prior_count": prior_count,
            "current_count": 0,
        }
        for topic, prior_count in prior_topic_counts.most_common()
        if prior_count >= MIN_TOPIC_COUNT and current_topic_counts.get(topic, 0) == 0
    ][:MAX_ORG_ITEMS]

    bus_factor = [
        {
            "topic": topic,
            "sole_expert": next(iter(members)),
            "sole_expert_name": member_names_by_id.get(next(iter(members)), "Unknown"),
            "count": current_topic_counts.get(topic, 0),
        }
        for topic, members in topic_members.items()
        if len(members) == 1 and current_topic_counts.get(topic, 0) >= MIN_TOPIC_COUNT
    ][:MAX_ORG_ITEMS]

    # Top contributors this window.
    member_counts: Counter[str] = Counter()
    for r in current_rows:
        if r.member_id:
            member_counts[r.member_id] += 1

    top_members = [
        {
            "member_id": mid,
            "name": member_names_by_id.get(mid, mid),
            "count": count,
        }
        for mid, count in member_counts.most_common(MAX_ORG_TOP_MEMBERS)
    ]

    return {
        "computed_at": computed_at.isoformat(),
        "organization_id": org_id,
        "member_count": len(member_ids),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "bus_factor": bus_factor,
        "top_members": top_members,
    }


def compute_and_save_strengths_weaknesses(
    db: Session,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Update member.strengths / .weaknesses and org.strengths_weaknesses_json.

    Returns a summary payload so the scheduler run has a usable result.
    """
    current = now or datetime.now(UTC)
    current_cutoff = current - timedelta(days=CURRENT_WINDOW_DAYS)
    prior_cutoff = current - timedelta(days=PRIOR_WINDOW_DAYS)

    members = db.query(MemberRecord).all()
    member_names_by_id = {m.id: m.name for m in members}

    # Bucket rows by member + window in a single pass so huge orgs stay cheap.
    current_rows_by_member: dict[str, list[ContributionRecord]] = defaultdict(list)
    prior_rows_by_member: dict[str, list[ContributionRecord]] = defaultdict(list)

    window_rows = (
        db.query(ContributionRecord)
        .filter(ContributionRecord.timestamp >= prior_cutoff)
        .all()
    )
    for r in window_rows:
        if not r.member_id:
            continue
        if r.timestamp is None:
            continue
        if r.timestamp >= current_cutoff:
            current_rows_by_member[r.member_id].append(r)
        else:
            prior_rows_by_member[r.member_id].append(r)

    members_updated = 0
    for member in members:
        strengths, weaknesses = _member_strengths_and_weaknesses(
            current_rows_by_member.get(member.id, []),
            prior_rows_by_member.get(member.id, []),
        )
        # Only write if either list is non-empty OR we need to clear stale data.
        prev_strengths = member.strengths or []
        prev_weaknesses = member.weaknesses or []
        if strengths != prev_strengths or weaknesses != prev_weaknesses:
            member.strengths = strengths
            member.weaknesses = weaknesses
            members_updated += 1

    # Aggregate per-org from the same cached buckets.
    members_by_org: dict[str | None, list[MemberRecord]] = defaultdict(list)
    for m in members:
        members_by_org[m.organization_id].append(m)

    orgs_updated = 0
    org_summaries: dict[str, dict[str, Any]] = {}
    for org_id, org_members in members_by_org.items():
        if org_id is None:
            continue
        member_ids = [m.id for m in org_members]
        current_rows = [r for mid in member_ids for r in current_rows_by_member.get(mid, [])]
        prior_rows = [r for mid in member_ids for r in prior_rows_by_member.get(mid, [])]

        summary = _org_summary(
            org_id=org_id,
            member_ids=member_ids,
            current_rows=current_rows,
            prior_rows=prior_rows,
            member_names_by_id=member_names_by_id,
            computed_at=current,
        )
        org_summaries[org_id] = summary

        org = db.query(OrganizationRecord).filter(OrganizationRecord.id == org_id).first()
        if org is not None:
            org.strengths_weaknesses_json = summary
            orgs_updated += 1

    db.commit()

    result = {
        "computed_at": current.isoformat(),
        "members_processed": len(members),
        "members_updated": members_updated,
        "orgs_updated": orgs_updated,
        "org_summaries": org_summaries,
    }
    logger.info(
        "Strengths/weaknesses complete: members_updated=%d orgs_updated=%d",
        members_updated,
        orgs_updated,
    )
    return result


def run_strengths_weaknesses_job() -> dict[str, Any]:
    """Scheduler entrypoint — opens its own session."""
    from app.db.database import create_session

    db = create_session()
    try:
        return compute_and_save_strengths_weaknesses(db)
    finally:
        db.close()
