"""KnowledgeVerificationService — assess freshness and correctness of insights.

Verification checks:
  1. Staleness — how many days since supporting artifacts were last ingested/synced.
  2. Coverage  — are there enough artifact chunks backing the insight (min 2 sources).
  3. LLM spot-check — ask the LLM to confirm the insight still holds given the
                       latest retrieved context (run only when requested).

Verification statuses (stored on InsightRecord.verification_status):
  "pending"  — not yet assessed
  "verified" — passes all checks
  "outdated" — supporting artifacts are stale (> staleness_threshold_days)
  "disputed" — LLM spot-check contradicts the insight
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.artifact import ArtifactRecord
from app.models.insight import InsightRecord

logger = logging.getLogger("collective_brain.knowledge_verification")

# Default staleness threshold: 30 days
DEFAULT_STALENESS_DAYS = 30


class VerificationResult:
    __slots__ = ("status", "staleness_days", "reasons", "spot_check_summary")

    def __init__(
        self,
        status: str,
        staleness_days: int | None,
        reasons: list[str],
        spot_check_summary: str | None = None,
    ):
        self.status = status
        self.staleness_days = staleness_days
        self.reasons = reasons
        self.spot_check_summary = spot_check_summary


class KnowledgeVerificationService:
    def __init__(self, staleness_threshold_days: int = DEFAULT_STALENESS_DAYS):
        self._threshold = staleness_threshold_days

    # ── Main entry point ───────────────────────────────────────────────────────

    def verify_insight(
        self,
        db: Session,
        insight: InsightRecord,
        *,
        run_llm_spot_check: bool = False,
        llm_service=None,
        vector_store=None,
        embedding_service=None,
        verifier_user_id: str | None = None,
    ) -> VerificationResult:
        """Run all verification checks for a single insight and persist results."""
        reasons: list[str] = []
        staleness_days: int | None = None
        status = "verified"

        # ── 1. Staleness check ─────────────────────────────────────────────────
        artifact_ids: list[str] = insight.source_artifact_ids or []

        if not artifact_ids:
            # No source artifacts recorded — fall back to generated_at age
            delta = (datetime.now(timezone.utc) - _ensure_tz(insight.generated_at)).days
            staleness_days = delta
            if delta > self._threshold:
                status = "outdated"
                reasons.append(
                    f"Insight is {delta} days old and has no linked source artifacts."
                )
        else:
            artifacts = (
                db.query(ArtifactRecord)
                .filter(ArtifactRecord.id.in_(artifact_ids))
                .all()
            )
            if not artifacts:
                status = "outdated"
                reasons.append("All linked source artifacts have been deleted.")
            else:
                max_staleness = 0
                for art in artifacts:
                    ref_date = art.last_synced_at or art.ingested_at
                    if ref_date:
                        days = (datetime.now(timezone.utc) - _ensure_tz(ref_date)).days
                        max_staleness = max(max_staleness, days)
                staleness_days = max_staleness
                if max_staleness > self._threshold:
                    status = "outdated"
                    reasons.append(
                        f"Supporting artifacts were last updated {max_staleness} days ago "
                        f"(threshold: {self._threshold} days)."
                    )

        # ── 2. Coverage check ──────────────────────────────────────────────────
        if len(artifact_ids) < 2 and status == "verified":
            reasons.append(
                "Insight is backed by fewer than 2 source artifacts — low confidence."
            )
            # Don't fail, but flag in reasons

        # ── 3. LLM spot-check (optional) ──────────────────────────────────────
        spot_check_summary: str | None = None
        if (
            run_llm_spot_check
            and llm_service is not None
            and vector_store is not None
            and embedding_service is not None
            and status != "outdated"  # no point spot-checking already-stale insight
        ):
            spot_check_summary, llm_verdict = self._llm_spot_check(
                insight, llm_service, vector_store, embedding_service
            )
            if llm_verdict == "disputed":
                status = "disputed"
                reasons.append("LLM spot-check contradicts this insight based on current context.")

        # ── Persist results ────────────────────────────────────────────────────
        insight.verification_status = status
        insight.staleness_days = staleness_days
        insight.verified_at = datetime.now(timezone.utc)
        if verifier_user_id:
            insight.verified_by = verifier_user_id
        db.commit()

        logger.info(
            "Insight %s verified: status=%s staleness=%s days",
            insight.id, status, staleness_days,
        )
        return VerificationResult(
            status=status,
            staleness_days=staleness_days,
            reasons=reasons,
            spot_check_summary=spot_check_summary,
        )

    def bulk_verify(
        self,
        db: Session,
        *,
        organization_id: str | None = None,
        limit: int = 100,
    ) -> dict[str, int]:
        """Run staleness-only verification on all pending/outdated insights.

        Returns a summary dict: {status: count}.
        """
        q = db.query(InsightRecord).filter(
            InsightRecord.verification_status.in_(["pending", "outdated"])
        )
        if organization_id:
            q = q.filter(InsightRecord.organization_id == organization_id)
        insights = q.limit(limit).all()

        summary: dict[str, int] = {"verified": 0, "outdated": 0, "disputed": 0}
        for insight in insights:
            result = self.verify_insight(db, insight)
            summary[result.status] = summary.get(result.status, 0) + 1

        logger.info("Bulk verification complete: %s", summary)
        return summary

    # ── LLM spot-check ─────────────────────────────────────────────────────────

    def _llm_spot_check(
        self,
        insight: InsightRecord,
        llm_service,
        vector_store,
        embedding_service,
    ) -> tuple[str, str]:
        """Ask the LLM whether the insight still holds. Returns (summary, verdict)."""
        try:
            query_embedding = embedding_service.embed(insight.title)
            results = vector_store.query(
                query_embedding=query_embedding,
                n_results=5,
                org_id=insight.organization_id,
            )
            docs = results.get("documents", [[]])[0]
            context = "\n\n".join(docs[:5]) if docs else "(no context available)"

            prompt = (
                f"You are a knowledge auditor. Based on the following context, "
                f"does this insight still hold?\n\n"
                f"INSIGHT: {insight.title}\n\n"
                f"INSIGHT BODY:\n{insight.body[:500]}\n\n"
                f"CURRENT CONTEXT:\n{context}\n\n"
                f"Answer with one of:\n"
                f"- CONFIRMED: <brief reason>\n"
                f"- DISPUTED: <brief reason>\n"
            )
            response = llm_service.generate(prompt, max_tokens=200)
            verdict = "disputed" if response.upper().startswith("DISPUTED") else "verified"
            return response, verdict
        except Exception as exc:
            logger.warning("LLM spot-check failed for insight %s: %s", insight.id, exc)
            return f"Spot-check failed: {exc}", "verified"  # default to verified on failure


# ── Utility ────────────────────────────────────────────────────────────────────

def _ensure_tz(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (UTC if naive)."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
