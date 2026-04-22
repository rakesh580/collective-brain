"""Idempotent backfill that re-canonicalizes topics already in the database.

Historical rows have polluted ContributionRecord.topics and
MemberRecord.expertise_tags (sentence fragments, commit subjects, etc.).
This service runs every row through the canonical allowlist and rewrites
the cleaned set back. Safe to run multiple times — it produces the same
output on repeated invocations.

Usage
-----
- From code: ``BackfillResult = run_topic_backfill(db)``
- Admin endpoint: ``POST /api/v1/admin/backfill-topics``
- CLI: ``python -m scripts.backfill_topics``
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ingestion.topic_extractor import canonicalize_list
from app.models.contribution import ContributionRecord
from app.models.member import MemberRecord

logger = logging.getLogger("collective_brain.topic_backfill")


@dataclass
class BackfillResult:
    contributions_scanned: int = 0
    contributions_changed: int = 0
    members_scanned: int = 0
    members_changed: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "contributions_scanned": self.contributions_scanned,
            "contributions_changed": self.contributions_changed,
            "members_scanned": self.members_scanned,
            "members_changed": self.members_changed,
        }


def _normalize_list_for_compare(lst: list[str] | None) -> list[str]:
    """Return a sorted, deduped copy for comparison purposes."""
    return sorted({s for s in (lst or []) if s})


def run_topic_backfill(db: Session, *, dry_run: bool = False) -> BackfillResult:
    """Recanonicalize topics on every contribution and member.

    Parameters
    ----------
    db : Session
        Caller-managed DB session. This function does not commit unless
        ``dry_run`` is False; callers should wrap in their own transaction
        boundary if they want finer control.
    dry_run : bool
        When True, returns counts without writing anything.
    """
    result = BackfillResult()

    # Pass 1 — canonicalize every contribution's topics
    contributions = db.query(ContributionRecord).all()
    for c in contributions:
        result.contributions_scanned += 1
        old = _normalize_list_for_compare(c.topics or [])
        new = canonicalize_list(c.topics or [])
        if old != new:
            result.contributions_changed += 1
            if not dry_run:
                c.topics = new

    # Pass 2 — rebuild members.expertise_tags from the now-clean contributions.
    # We rebuild from the current canonicalized c.topics (not the raw tags),
    # which converges on a consistent state even if a member was touched only
    # by historical noise. Declared skills from UserRecord are out of scope.
    members = db.query(MemberRecord).all()
    for m in members:
        result.members_scanned += 1
        # Collect topics across this member's contributions
        member_contribs = [c for c in contributions if c.member_id == m.id]
        rebuilt: set[str] = set()
        for c in member_contribs:
            for t in c.topics or []:
                rebuilt.add(t)
        # Also canonicalize any existing tags in case we haven't rebuilt
        # from contributions (defensive — keeps expertise stable for members
        # whose contributions haven't been re-ingested yet).
        for t in canonicalize_list(m.expertise_tags or []):
            rebuilt.add(t)

        new_tags = sorted(rebuilt)
        old_tags = _normalize_list_for_compare(m.expertise_tags or [])
        if old_tags != new_tags:
            result.members_changed += 1
            if not dry_run:
                m.expertise_tags = new_tags

    if not dry_run:
        db.commit()

    logger.info(
        "topic_backfill complete: contributions=%d changed=%d members=%d changed=%d dry_run=%s",
        result.contributions_scanned,
        result.contributions_changed,
        result.members_scanned,
        result.members_changed,
        dry_run,
    )
    return result
