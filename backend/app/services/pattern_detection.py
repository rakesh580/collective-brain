"""Nightly pattern-detection service.

Five detectors surface actionable patterns in the org's recent activity.
Each produces zero or more ``PendingSignal`` dataclasses that the
orchestrator upserts into the ``signals`` table — one open signal per
``(organization_id, dedup_key)``. Repeated nightly detections update
the existing row instead of spamming new ones.

Detectors (v1):

1. **Slow lanes** — topics whose completed work_items take >= 2× the team
   median cycle time. Fires when topic has >= 3 completed items.
2. **Silent areas** — topics with >= 10 contributions in the prior 76-day
   window (day 14-90 ago) and 0 in the last 14d.
3. **Load skew** — topics where one member owns >= 60% of the last-90-day
   contributions, with >= 3 distinct contributors and >= 10 total items.
4. **Friday-land** — Friday merges whose p50 cycle time is >= 1.5× the
   other-weekday p50. Fires per-org (singleton signal).
5. **Review bottleneck** — in the last 7d, count PRs whose first review
   came > 24h after open, plus open PRs with no review and > 24h old.
   Fires when the combined count > 3.

Every detector is a pure function over the DB session — trivially unit
testable with synthetic fixtures. The orchestrator (``run_pattern_detection``)
opens its own session for the scheduler.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

from sqlalchemy.orm import Session

from app.models.contribution import ContributionRecord
from app.models.organization import OrganizationRecord
from app.models.signal import Signal
from app.models.work_item import WorkItem

logger = logging.getLogger("collective_brain.pattern_detection")


@dataclass
class PendingSignal:
    signal_type: str
    severity: str
    title: str
    description: str
    evidence: dict[str, Any]
    suggested_action: str
    dedup_key: str
    organization_id: str | None = None
    # Ephemeral — defaults filled by the orchestrator on insert.
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# ── Helpers ─────────────────────────────────────────────────────────────────


def _severity_from_ratio(ratio: float, thresholds: tuple[float, float]) -> str:
    """Map a ratio to severity bucket. thresholds = (medium_min, high_min)."""
    if ratio >= thresholds[1]:
        return "high"
    if ratio >= thresholds[0]:
        return "medium"
    return "low"


def _percentile(values: list[float], p: float) -> float | None:
    """Simple inclusive percentile. Returns None on empty input."""
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p
    low = int(k)
    high = min(low + 1, len(s) - 1)
    frac = k - low
    return s[low] * (1 - frac) + s[high] * frac


def _naive_to_utc(ts: datetime | None) -> datetime | None:
    if ts is None:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


# ── Detectors ───────────────────────────────────────────────────────────────


def detect_slow_lanes(
    db: Session,
    organization_id: str | None,
    now: datetime,
    *,
    min_items_per_topic: int = 3,
    flag_ratio: float = 2.0,
) -> list[PendingSignal]:
    """Topics whose p50 cycle time exceeds `flag_ratio` * team median."""
    cutoff = now - timedelta(days=90)
    items = (
        db.query(WorkItem)
        .filter(
            WorkItem.cycle_time_hours.isnot(None),
            WorkItem.state.in_(("merged", "closed")),
            WorkItem.completed_at >= cutoff,
        )
        .all()
    )

    all_times = [w.cycle_time_hours for w in items if w.cycle_time_hours is not None]
    if len(all_times) < min_items_per_topic:
        return []
    team_median = median(all_times)
    if team_median <= 0:
        return []

    topic_times: dict[str, list[float]] = defaultdict(list)
    topic_items: dict[str, list[str]] = defaultdict(list)
    for w in items:
        if w.cycle_time_hours is None:
            continue
        for t in w.topics or []:
            if not t:
                continue
            topic_times[t].append(w.cycle_time_hours)
            topic_items[t].append(w.id)

    signals: list[PendingSignal] = []
    for topic, times in topic_times.items():
        if len(times) < min_items_per_topic:
            continue
        topic_p50 = median(times)
        ratio = topic_p50 / team_median
        if ratio < flag_ratio:
            continue
        severity = _severity_from_ratio(ratio, (3.0, 4.0))
        # Pick the 5 slowest as evidence.
        slowest_ids = [wid for _, wid in sorted(zip(times, topic_items[topic], strict=False), reverse=True)][:5]
        signals.append(
            PendingSignal(
                signal_type="slow_lane",
                severity=severity,
                title=f"Slow lane: '{topic}' PRs take {ratio:.1f}× the team median",
                description=(
                    f"Topic '{topic}' has a p50 cycle time of {topic_p50:.1f}h "
                    f"vs the team median of {team_median:.1f}h "
                    f"over {len(times)} completed items in the last 90 days."
                ),
                evidence={
                    "topic": topic,
                    "topic_p50_hours": round(topic_p50, 2),
                    "team_median_hours": round(team_median, 2),
                    "ratio": round(ratio, 2),
                    "sample_size": len(times),
                    "work_item_ids": slowest_ids,
                },
                suggested_action=(
                    f"Pair on a '{topic}' PR to surface the blockers — reviewer "
                    f"queue, test flakiness, or unclear acceptance criteria."
                ),
                dedup_key=f"slow_lane:{topic}",
                organization_id=organization_id,
                detected_at=now,
            )
        )
    return signals


def detect_silent_areas(
    db: Session,
    organization_id: str | None,
    now: datetime,
    *,
    prior_window_days: int = 90,
    recent_window_days: int = 14,
    min_prior_count: int = 10,
) -> list[PendingSignal]:
    """Topics active in the prior 76-day window but silent in the last 14d."""
    recent_cutoff = now - timedelta(days=recent_window_days)
    prior_cutoff = now - timedelta(days=prior_window_days)

    contribs = db.query(ContributionRecord).filter(ContributionRecord.timestamp >= prior_cutoff).all()

    prior_counts: Counter[str] = Counter()
    recent_counts: Counter[str] = Counter()
    last_activity: dict[str, datetime] = {}

    for c in contribs:
        ts = _naive_to_utc(c.timestamp)
        if ts is None:
            continue
        for t in c.topics or []:
            if not t:
                continue
            if ts >= recent_cutoff:
                recent_counts[t] += 1
            else:
                prior_counts[t] += 1
            if t not in last_activity or ts > last_activity[t]:
                last_activity[t] = ts

    signals: list[PendingSignal] = []
    for topic, prior in prior_counts.items():
        if prior < min_prior_count:
            continue
        if recent_counts.get(topic, 0) > 0:
            continue  # Still active.
        severity = "high" if prior >= 30 else "medium" if prior >= 20 else "low"
        last_ts = last_activity.get(topic)
        signals.append(
            PendingSignal(
                signal_type="silent_area",
                severity=severity,
                title=f"Silent area: '{topic}' hasn't seen activity in 14 days",
                description=(
                    f"Topic '{topic}' had {prior} contributions in the prior "
                    f"{prior_window_days - recent_window_days} days but zero in the "
                    f"last {recent_window_days} days. Knowledge risks going stale."
                ),
                evidence={
                    "topic": topic,
                    "prior_count": prior,
                    "recent_count": 0,
                    "prior_window_days": prior_window_days - recent_window_days,
                    "recent_window_days": recent_window_days,
                    "last_activity_at": last_ts.isoformat() if last_ts else None,
                },
                suggested_action=(
                    f"Assign a DRI to review the '{topic}' surface — refresh docs, "
                    f"ping the past contributors, or archive if intentionally paused."
                ),
                dedup_key=f"silent_area:{topic}",
                organization_id=organization_id,
                detected_at=now,
            )
        )
    return signals


def detect_load_skew(
    db: Session,
    organization_id: str | None,
    now: datetime,
    *,
    window_days: int = 90,
    min_contributors: int = 3,
    min_topic_total: int = 10,
    skew_threshold: float = 0.60,
) -> list[PendingSignal]:
    """Topics where one member owns >= 60% of activity."""
    cutoff = now - timedelta(days=window_days)
    contribs = db.query(ContributionRecord).filter(ContributionRecord.timestamp >= cutoff).all()

    per_topic_member: dict[str, Counter[str]] = defaultdict(Counter)
    for c in contribs:
        if not c.member_id:
            continue
        for t in c.topics or []:
            if t:
                per_topic_member[t][c.member_id] += 1

    signals: list[PendingSignal] = []
    for topic, members in per_topic_member.items():
        total = sum(members.values())
        if total < min_topic_total or len(members) < min_contributors:
            continue
        top_member, top_count = members.most_common(1)[0]
        share = top_count / total
        if share < skew_threshold:
            continue
        severity = "high" if share >= 0.85 else "medium" if share >= 0.75 else "low"
        signals.append(
            PendingSignal(
                signal_type="load_skew",
                severity=severity,
                title=f"Load skew: one person owns {share * 100:.0f}% of '{topic}'",
                description=(
                    f"Member '{top_member}' authored {top_count} of {total} "
                    f"contributions to '{topic}' in the last {window_days} days "
                    f"({len(members)} total contributors). Bus-factor risk."
                ),
                evidence={
                    "topic": topic,
                    "top_contributor_id": top_member,
                    "top_contributor_share": round(share, 3),
                    "top_contributor_count": top_count,
                    "total_contributors": len(members),
                    "total_contributions": total,
                    "window_days": window_days,
                },
                suggested_action=(
                    f"Pair {top_member} with a second owner on '{topic}' in the next "
                    f"sprint. Reassign incoming tickets in this area."
                ),
                dedup_key=f"load_skew:{topic}",
                organization_id=organization_id,
                detected_at=now,
            )
        )
    return signals


def detect_friday_land(
    db: Session,
    organization_id: str | None,
    now: datetime,
    *,
    window_days: int = 90,
    ratio_threshold: float = 1.5,
    min_friday_sample: int = 5,
) -> list[PendingSignal]:
    """Friday merges whose p50 cycle time significantly exceeds other weekdays'."""
    cutoff = now - timedelta(days=window_days)
    items = (
        db.query(WorkItem)
        .filter(
            WorkItem.state.in_(("merged", "closed")),
            WorkItem.cycle_time_hours.isnot(None),
            WorkItem.completed_at >= cutoff,
        )
        .all()
    )

    friday_times: list[float] = []
    other_times: list[float] = []
    friday_ids: list[str] = []
    for w in items:
        completed = _naive_to_utc(w.completed_at)
        if completed is None or w.cycle_time_hours is None:
            continue
        if completed.weekday() == 4:  # Friday
            friday_times.append(w.cycle_time_hours)
            friday_ids.append(w.id)
        else:
            other_times.append(w.cycle_time_hours)

    if len(friday_times) < min_friday_sample or len(other_times) < min_friday_sample:
        return []

    friday_p50 = median(friday_times)
    other_p50 = median(other_times)
    if other_p50 <= 0:
        return []
    ratio = friday_p50 / other_p50
    if ratio < ratio_threshold:
        return []

    severity = _severity_from_ratio(ratio, (1.7, 2.0))
    return [
        PendingSignal(
            signal_type="friday_land",
            severity=severity,
            title=f"Friday-land: Friday merges are {ratio:.1f}× slower than other days",
            description=(
                f"Over the last {window_days} days, Friday-completed PRs have a "
                f"p50 cycle time of {friday_p50:.1f}h vs {other_p50:.1f}h on other "
                f"weekdays (n_friday={len(friday_times)}, n_other={len(other_times)})."
            ),
            evidence={
                "friday_p50_hours": round(friday_p50, 2),
                "other_days_p50_hours": round(other_p50, 2),
                "ratio": round(ratio, 2),
                "friday_sample": len(friday_times),
                "other_sample": len(other_times),
                "work_item_ids": friday_ids[:5],
            },
            suggested_action=(
                "Cut off merges at Thursday EOD unless critical. Friday merges "
                "correlate with longer review loops and weekend regressions."
            ),
            dedup_key="friday_land",
            organization_id=organization_id,
            detected_at=now,
        )
    ]


def detect_review_bottlenecks(
    db: Session,
    organization_id: str | None,
    now: datetime,
    *,
    window_days: int = 7,
    review_sla_hours: float = 24.0,
    flag_threshold: int = 3,
) -> list[PendingSignal]:
    """Count PRs in the last week with slow first review, plus still-open PRs past SLA."""
    cutoff = now - timedelta(days=window_days)
    items = db.query(WorkItem).filter(WorkItem.source == "github_pr", WorkItem.created_at >= cutoff).all()

    slow_reviewed: list[str] = []
    stuck_open: list[str] = []
    for w in items:
        created = _naive_to_utc(w.created_at)
        started = _naive_to_utc(w.started_at)
        if created is None:
            continue
        if started is not None:
            hours = (started - created).total_seconds() / 3600.0
            if hours > review_sla_hours:
                slow_reviewed.append(w.id)
        elif w.state == "open":
            hours = (now - created).total_seconds() / 3600.0
            if hours > review_sla_hours:
                stuck_open.append(w.id)

    total_flagged = len(slow_reviewed) + len(stuck_open)
    if total_flagged <= flag_threshold:
        return []

    severity = "high" if total_flagged >= 10 else "medium" if total_flagged >= 6 else "low"
    return [
        PendingSignal(
            signal_type="review_bottleneck",
            severity=severity,
            title=f"Review bottleneck: {total_flagged} PRs exceeded the {int(review_sla_hours)}h review SLA this week",
            description=(
                f"In the last {window_days} days, {len(slow_reviewed)} PRs received "
                f"their first review only after > {int(review_sla_hours)}h, and "
                f"{len(stuck_open)} PRs are still open with no review past the SLA."
            ),
            evidence={
                "slow_reviewed_count": len(slow_reviewed),
                "stuck_open_count": len(stuck_open),
                "sla_hours": review_sla_hours,
                "window_days": window_days,
                "work_item_ids": (slow_reviewed + stuck_open)[:10],
            },
            suggested_action=(
                "Rebalance review load — pair up reviewers, set up a shared queue, or auto-assign via CODEOWNERS."
            ),
            dedup_key="review_bottleneck",
            organization_id=organization_id,
            detected_at=now,
        )
    ]


# ── Orchestrator ────────────────────────────────────────────────────────────


DETECTORS: list[Callable[..., list[PendingSignal]]] = [
    detect_slow_lanes,
    detect_silent_areas,
    detect_load_skew,
    detect_friday_land,
    detect_review_bottlenecks,
]


def _upsert_signal(db: Session, pending: PendingSignal) -> Signal:
    """Merge a newly-detected signal with any existing OPEN row for the same key."""
    existing = (
        db.query(Signal)
        .filter(
            Signal.organization_id == pending.organization_id,
            Signal.dedup_key == pending.dedup_key,
            Signal.resolved_at.is_(None),
        )
        .first()
    )

    if existing is None:
        row = Signal(
            id=str(uuid.uuid4()),
            organization_id=pending.organization_id,
            signal_type=pending.signal_type,
            severity=pending.severity,
            title=pending.title,
            description=pending.description,
            evidence=pending.evidence,
            suggested_action=pending.suggested_action,
            dedup_key=pending.dedup_key,
            detected_at=pending.detected_at,
        )
        db.add(row)
        _record_signal_metric(pending, outcome="created")
        return row

    # Refresh fields — severity / evidence / title may have shifted since last run.
    existing.severity = pending.severity
    existing.title = pending.title
    existing.description = pending.description
    existing.evidence = pending.evidence
    existing.suggested_action = pending.suggested_action
    existing.detected_at = pending.detected_at
    _record_signal_metric(pending, outcome="updated")
    return existing


def _record_signal_metric(pending: PendingSignal, outcome: str) -> None:
    """Increment the signals-detected counter. Failure is logged but never
    propagates — a metrics outage must not break the nightly job."""
    try:
        from app.services.metrics import SIGNALS_DETECTED_TOTAL

        SIGNALS_DETECTED_TOTAL.labels(
            signal_type=pending.signal_type,
            severity=pending.severity,
            outcome=outcome,
        ).inc()
    except Exception:  # pragma: no cover — metrics must never break detection
        logger.warning("Could not record signal detection metric", exc_info=True)


def run_pattern_detection_for_org(
    db: Session,
    organization_id: str | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Per-org runner. Runs every detector against one tenant and upserts
    signals. The orchestrator's per-org loop calls this so a detector
    raising for org A cannot block detection for org B."""
    from app.services.nightly_pipeline import current_pipeline_as_of

    current = now or current_pipeline_as_of()

    created = 0
    updated = 0
    for detector in DETECTORS:
        try:
            pending_list = detector(db, organization_id, current)
        except Exception:
            logger.exception("Detector %s failed for org=%s", detector.__name__, organization_id)
            continue
        for pending in pending_list:
            existed_before = (
                db.query(Signal.id)
                .filter(
                    Signal.organization_id == organization_id,
                    Signal.dedup_key == pending.dedup_key,
                    Signal.resolved_at.is_(None),
                )
                .first()
            )
            _upsert_signal(db, pending)
            if existed_before is None:
                created += 1
            else:
                updated += 1

    db.commit()
    return {
        "organization_id": organization_id,
        "detectors_run": len(DETECTORS),
        "signals_created": created,
        "signals_updated": updated,
        "ran_at": current.isoformat(),
    }


def run_pattern_detection(db: Session, now: datetime | None = None) -> dict[str, Any]:
    """Run every detector across every active org and upsert signals.
    Thin wrapper that fans out to ``run_pattern_detection_for_org``."""
    from app.services.nightly_pipeline import current_pipeline_as_of

    current = now or current_pipeline_as_of()

    orgs = db.query(OrganizationRecord).filter(OrganizationRecord.is_active == True).all()  # noqa: E712
    # Always run at least once for the "no org" case (self-hosted single-org).
    org_ids: list[str | None] = [o.id for o in orgs] or [None]

    created = 0
    updated = 0
    for org_id in org_ids:
        per = run_pattern_detection_for_org(db, org_id, now=current)
        created += per["signals_created"]
        updated += per["signals_updated"]

    summary = {
        "orgs_scanned": len(org_ids),
        "detectors_run": len(DETECTORS),
        "signals_created": created,
        "signals_updated": updated,
        "ran_at": current.isoformat(),
    }
    logger.info(
        "Pattern detection complete: orgs=%d created=%d updated=%d",
        summary["orgs_scanned"],
        created,
        updated,
    )
    return summary


def run_pattern_detection_job() -> dict[str, Any]:
    """Scheduler entrypoint. Opens its own DB session per run."""
    from app.db.database import create_session

    db = create_session()
    try:
        return run_pattern_detection(db)
    finally:
        db.close()
