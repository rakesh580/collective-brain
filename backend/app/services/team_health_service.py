"""Team Health Trends — compute, persist, and predict team health metrics."""

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.memory_graph import MemoryGraph

logger = logging.getLogger("collective_brain.team_health")


def compute_health_snapshot(db: Session) -> dict:
    """Calculate current team health metrics from the knowledge graph."""
    mg = MemoryGraph(db)
    G = mg._get_or_build_nx_graph()

    # ── Collect node sets ──
    member_nodes = {
        nid: d for nid, d in G.nodes(data=True) if d.get("node_type") == "member"
    }
    topic_nodes = {
        nid: d for nid, d in G.nodes(data=True) if d.get("node_type") == "topic"
    }

    total_topics = len(topic_nodes)
    total_members = len(member_nodes)

    # ── 1. Bus factor count (topics with <= 1 expert) ──
    bus_factor_topics: list[dict] = []
    topics_with_2_plus = 0

    for tid, tdata in topic_nodes.items():
        member_experts = [
            n for n in G.neighbors(tid)
            if G.nodes[n].get("node_type") == "member"
        ]
        if len(member_experts) <= 1:
            expert_names = [
                G.nodes[m].get("label", m) for m in member_experts
            ]
            bus_factor_topics.append({
                "topic": tdata.get("label", tid),
                "expert_count": len(member_experts),
                "experts": expert_names,
            })
        if len(member_experts) >= 2:
            topics_with_2_plus += 1

    bus_factor_count = len(bus_factor_topics)

    # ── 2. Knowledge coverage % ──
    coverage_pct = round(
        (topics_with_2_plus / max(1, total_topics)) * 100, 1
    )

    # ── 3. Collaboration density ──
    collab_edges = sum(
        1 for _, _, d in G.edges(data=True)
        if d.get("edge_type") == "COLLABORATED_WITH"
    )
    possible_member_edges = total_members * (total_members - 1) / 2 if total_members > 1 else 1
    collab_density = round(collab_edges / possible_member_edges, 4)

    # ── 4. Active member % (last 30 days) ──
    contribs = mg._query_contributions()
    now = datetime.now(UTC)
    cutoff_30d = now - timedelta(days=30)
    member_last_active: dict[str, datetime] = {}
    for c in contribs:
        if c.timestamp and c.member_id:
            prev = member_last_active.get(c.member_id)
            if prev is None or c.timestamp > prev:
                member_last_active[c.member_id] = c.timestamp

    active_members = sum(
        1 for mid in member_nodes
        if member_last_active.get(mid) and member_last_active[mid] >= cutoff_30d
    )
    active_member_pct = round(
        (active_members / max(1, total_members)) * 100, 1
    )

    # ── 5. Average expertise breadth ──
    breadths: list[int] = []
    for mid in member_nodes:
        topic_count = sum(
            1 for nbr in G.neighbors(mid)
            if G.nodes[nbr].get("node_type") == "topic"
        )
        breadths.append(topic_count)
    avg_breadth = round(sum(breadths) / max(1, len(breadths)), 2)

    # ── 6. Overall health score (0-100 weighted composite) ──
    # Weights: coverage 30%, active 25%, collab 20%, breadth 15%, bus_factor_inv 10%
    coverage_score = min(coverage_pct, 100)
    active_score = min(active_member_pct, 100)
    collab_score = min(collab_density * 100, 100)  # density is 0-1
    breadth_score = min(avg_breadth / max(1, total_topics) * 100, 100) if total_topics > 0 else 0
    # Bus factor inverse: fewer bus factor topics = better
    bus_factor_inv = max(0, 100 - (bus_factor_count / max(1, total_topics)) * 100)

    health_score = round(
        coverage_score * 0.30
        + active_score * 0.25
        + collab_score * 0.20
        + breadth_score * 0.15
        + bus_factor_inv * 0.10,
        1,
    )

    # ── 7. Top risk ──
    top_risk = None
    if bus_factor_topics:
        # Sort by expert_count ascending (worst first)
        worst = sorted(bus_factor_topics, key=lambda x: x["expert_count"])[0]
        top_risk = worst

    return {
        "bus_factor_count": bus_factor_count,
        "coverage_pct": coverage_pct,
        "collab_density": collab_density,
        "active_member_pct": active_member_pct,
        "avg_breadth": avg_breadth,
        "health_score": health_score,
        "top_risk": top_risk,
        "computed_at": now.isoformat(),
    }


def save_health_snapshot(db: Session) -> dict:
    """Persist a health snapshot with timestamp."""
    snapshot = compute_health_snapshot(db)
    snapshot_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    risk_summary = json.dumps(snapshot.get("top_risk") or {})

    db.execute(
        text(
            "INSERT INTO health_snapshots "
            "(id, timestamp, bus_factor_count, coverage_pct, collab_density, "
            "active_member_pct, avg_breadth, health_score, risk_summary, created_at) "
            "VALUES (:id, :timestamp, :bus_factor_count, :coverage_pct, :collab_density, "
            ":active_member_pct, :avg_breadth, :health_score, :risk_summary, :created_at)"
        ),
        {
            "id": snapshot_id,
            "timestamp": now,
            "bus_factor_count": snapshot["bus_factor_count"],
            "coverage_pct": snapshot["coverage_pct"],
            "collab_density": snapshot["collab_density"],
            "active_member_pct": snapshot["active_member_pct"],
            "avg_breadth": snapshot["avg_breadth"],
            "health_score": snapshot["health_score"],
            "risk_summary": risk_summary,
            "created_at": now,
        },
    )
    db.commit()

    return {
        "id": snapshot_id,
        "success": True,
        **snapshot,
    }


def get_health_trends(db: Session, period_days: int = 90) -> dict:
    """Return historical snapshots for charting."""
    cutoff = datetime.now(UTC) - timedelta(days=period_days)

    rows = db.execute(
        text(
            "SELECT id, timestamp, bus_factor_count, coverage_pct, collab_density, "
            "active_member_pct, avg_breadth, health_score, risk_summary "
            "FROM health_snapshots "
            "WHERE timestamp >= :cutoff "
            "ORDER BY timestamp ASC"
        ),
        {"cutoff": cutoff},
    ).fetchall()

    snapshots = []
    for row in rows:
        risk_raw = row[8]
        if isinstance(risk_raw, str):
            try:
                risk_parsed = json.loads(risk_raw)
            except (json.JSONDecodeError, TypeError):
                risk_parsed = {}
        else:
            risk_parsed = risk_raw or {}

        snapshots.append({
            "id": row[0],
            "timestamp": row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1]),
            "bus_factor_count": row[2],
            "coverage_pct": row[3],
            "collab_density": row[4],
            "active_member_pct": row[5],
            "avg_breadth": row[6],
            "health_score": row[7],
            "risk_summary": risk_parsed,
        })

    return {"snapshots": snapshots, "period_days": period_days}


def predict_risks(db: Session, horizon_days: int = 90) -> dict:
    """Simple linear extrapolation based on recent trends."""
    trends = get_health_trends(db, period_days=180)
    snapshots = trends["snapshots"]

    predictions: list[dict] = []

    metrics = [
        ("health_score", "Overall Health Score"),
        ("coverage_pct", "Knowledge Coverage"),
        ("bus_factor_count", "Bus Factor Count"),
        ("collab_density", "Collaboration Density"),
        ("active_member_pct", "Active Members"),
        ("avg_breadth", "Expertise Breadth"),
    ]

    for metric_key, metric_label in metrics:
        if len(snapshots) < 2:
            # Not enough data to predict
            current_val = snapshots[-1][metric_key] if snapshots else 0
            predictions.append({
                "metric": metric_label,
                "current_value": round(current_val, 2),
                "predicted_value": round(current_val, 2),
                "horizon_days": horizon_days,
                "trend": "stable",
                "risk_level": "low",
                "description": "Not enough historical data for prediction.",
            })
            continue

        # Linear regression on the metric values
        values = [s[metric_key] for s in snapshots]
        n = len(values)
        x_vals = list(range(n))
        x_mean = sum(x_vals) / n
        y_mean = sum(values) / n

        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, values))
        denominator = sum((x - x_mean) ** 2 for x in x_vals)

        slope = 0.0 if denominator == 0 else numerator / denominator

        current_val = values[-1]

        # Extrapolate: how many "snapshot intervals" into the future?
        # Assume roughly daily snapshots; project horizon_days forward
        if n >= 2:
            # Calculate avg interval between snapshots in days
            first_ts = snapshots[0]["timestamp"]
            last_ts = snapshots[-1]["timestamp"]
            try:
                from dateutil.parser import parse as parse_dt
                dt_first = parse_dt(first_ts) if isinstance(first_ts, str) else first_ts
                dt_last = parse_dt(last_ts) if isinstance(last_ts, str) else last_ts
                total_span = max((dt_last - dt_first).total_seconds() / 86400, 1)
            except Exception:
                total_span = max(n - 1, 1)
            avg_interval = total_span / max(n - 1, 1)
            steps_forward = horizon_days / max(avg_interval, 0.1)
        else:
            steps_forward = horizon_days

        predicted_val = current_val + slope * steps_forward

        # Determine trend
        change_pct = ((predicted_val - current_val) / max(abs(current_val), 0.01)) * 100

        if metric_key == "bus_factor_count":
            # Higher bus factor count is bad
            if change_pct > 10:
                trend = "declining"
            elif change_pct < -10:
                trend = "improving"
            else:
                trend = "stable"
        else:
            # Higher values are generally good
            if change_pct > 10:
                trend = "improving"
            elif change_pct < -10:
                trend = "declining"
            else:
                trend = "stable"

        # Risk level
        if trend == "declining":
            risk_level = "high" if abs(change_pct) > 25 else "medium"
        elif trend == "stable":
            risk_level = "low"
        else:
            risk_level = "low"

        # Description
        if trend == "improving":
            description = f"{metric_label} is trending upward and expected to improve over the next {horizon_days} days."
        elif trend == "declining":
            description = f"{metric_label} is trending downward. Consider taking action to prevent further decline."
        else:
            description = f"{metric_label} is stable with no significant change expected."

        predictions.append({
            "metric": metric_label,
            "current_value": round(current_val, 2),
            "predicted_value": round(predicted_val, 2),
            "horizon_days": horizon_days,
            "trend": trend,
            "risk_level": risk_level,
            "description": description,
        })

    return {"predictions": predictions}
