import logging

from sqlalchemy import or_

from app.db.database import create_session
from app.models.artifact import ArtifactRecord
from app.models.decision import DecisionLink, DecisionRecord
from app.models.member import MemberRecord
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.vector_store import VectorStoreService

logger = logging.getLogger("collective_brain.decisions.search")

WHY_DID_WE_PROMPT = """You are a decision intelligence assistant for a team. You help answer questions about past decisions by synthesizing information from the team's decision records.

A team member is asking: "{question}"

Here are the relevant decisions from the team's decision history:

{decisions_context}

Here is additional context from source artifacts:

{artifacts_context}

Based on these records, provide a clear, comprehensive answer to the question. Include:
1. A direct answer to the question
2. The reasoning and context behind the decision(s)
3. What alternatives were considered (if any)
4. Who was involved in making the decision
5. Any related or follow-up decisions

If the available records don't fully answer the question, say so clearly and explain what information is available.

Respond in a clear, professional tone. Do not invent information not present in the records."""


class DecisionSearchService:
    """Answers 'Why did we...' questions using the decision graph."""

    def __init__(
        self,
        llm_service: LLMService,
        embedding_service: EmbeddingService,
        vector_store: VectorStoreService,
    ):
        self.llm = llm_service
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    async def search_decisions(self, query: str, limit: int = 10, organization_id: str | None = None) -> list[dict]:
        """Search decisions by keyword and semantic similarity."""
        db = create_session()
        try:
            # Keyword search via ILIKE
            escaped_q = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped_q}%"

            keyword_query = db.query(DecisionRecord).filter(
                or_(
                    DecisionRecord.title.ilike(pattern),
                    DecisionRecord.description.ilike(pattern),
                    DecisionRecord.context_summary.ilike(pattern),
                )
            )
            if organization_id:
                keyword_query = keyword_query.filter(DecisionRecord.organization_id == organization_id)

            keyword_results = keyword_query.order_by(DecisionRecord.created_at.desc()).limit(limit).all()
            keyword_ids = {d.id for d in keyword_results}

            # Semantic search: embed query, compare against decision texts
            semantic_results = []
            try:
                query_embedding = self.embedding_service.embed(query)
                all_decisions = db.query(DecisionRecord)
                if organization_id:
                    all_decisions = all_decisions.filter(DecisionRecord.organization_id == organization_id)
                all_decisions = all_decisions.all()

                scored = []
                for decision in all_decisions:
                    if decision.id in keyword_ids:
                        continue
                    text = f"{decision.title}. {decision.description or ''} {decision.context_summary or ''}"
                    dec_embedding = self.embedding_service.embed(text)
                    similarity = self._cosine_similarity(query_embedding, dec_embedding)
                    if similarity > 0.5:
                        scored.append((decision, similarity))

                scored.sort(key=lambda x: x[1], reverse=True)
                semantic_results = [d for d, _ in scored[:limit]]
            except Exception as e:
                logger.warning("Semantic search failed, falling back to keyword only: %s", e)

            # Merge results: keyword first, then semantic
            merged = []
            seen_ids = set()
            for decision in keyword_results:
                if decision.id not in seen_ids:
                    merged.append(self._decision_to_dict(decision))
                    seen_ids.add(decision.id)
            for decision in semantic_results:
                if decision.id not in seen_ids and len(merged) < limit:
                    merged.append(self._decision_to_dict(decision))
                    seen_ids.add(decision.id)

            return merged

        finally:
            db.close()

    async def why_did_we(self, question: str, organization_id: str | None = None) -> dict:
        """Answer a 'why did we...' question.
        1. Search for relevant decisions
        2. Gather context (linked decisions, involved members, source artifacts)
        3. Use LLM to synthesize an answer with full provenance
        4. Return answer + decision trail + sources"""
        db = create_session()
        try:
            # Step 1: Find relevant decisions
            relevant_decisions = await self.search_decisions(question, limit=5, organization_id=organization_id)

            if not relevant_decisions:
                return {
                    "question": question,
                    "answer": "No relevant decisions were found in the team's decision history for this question.",
                    "confidence": 0.0,
                    "decision_trail": [],
                    "sources": [],
                    "related_members": [],
                }

            # Step 2: Gather richer context
            decision_ids = [d["id"] for d in relevant_decisions]
            all_source_artifact_ids = set()
            all_member_ids = set()
            linked_decisions = []

            for dec in relevant_decisions:
                for aid in dec.get("source_artifact_ids", []):
                    all_source_artifact_ids.add(aid)
                for mid in dec.get("involved_member_ids", []):
                    all_member_ids.add(mid)

            # Get linked decisions
            links = (
                db.query(DecisionLink)
                .filter(
                    or_(
                        DecisionLink.from_decision_id.in_(decision_ids),
                        DecisionLink.to_decision_id.in_(decision_ids),
                    )
                )
                .all()
            )
            linked_ids = set()
            for link in links:
                if link.from_decision_id not in decision_ids:
                    linked_ids.add(link.from_decision_id)
                if link.to_decision_id not in decision_ids:
                    linked_ids.add(link.to_decision_id)

            if linked_ids:
                extra_decisions = (
                    db.query(DecisionRecord)
                    .filter(DecisionRecord.id.in_(linked_ids))
                    .all()
                )
                for d in extra_decisions:
                    linked_decisions.append(self._decision_to_dict(d))

            # Get source artifacts
            source_artifacts = []
            if all_source_artifact_ids:
                artifacts = (
                    db.query(ArtifactRecord)
                    .filter(ArtifactRecord.id.in_(list(all_source_artifact_ids)))
                    .all()
                )
                for a in artifacts:
                    source_artifacts.append(
                        {
                            "id": a.id,
                            "title": a.title,
                            "source_type": a.source_type,
                            "source_path": a.source_path,
                            "ingested_at": a.ingested_at.isoformat() if a.ingested_at else None,
                        }
                    )

            # Get involved members
            related_members = []
            if all_member_ids:
                members = (
                    db.query(MemberRecord)
                    .filter(MemberRecord.id.in_(list(all_member_ids)))
                    .all()
                )
                for m in members:
                    related_members.append(
                        {
                            "id": m.id,
                            "name": m.name,
                            "expertise_tags": m.expertise_tags or [],
                        }
                    )

            # Also do vector search on source artifacts for extra context
            artifacts_context_text = ""
            try:
                query_embedding = self.embedding_service.embed(question)
                vector_results = self.vector_store.query(
                    query_embedding=query_embedding,
                    n_results=5,
                    organization_id=organization_id,
                )
                docs = vector_results.get("documents", [[]])[0] if vector_results.get("documents") else []
                if docs:
                    artifacts_context_text = "\n\n".join(docs[:5])
            except Exception as e:
                logger.warning("Vector search for why_did_we context failed: %s", e)

            # Step 3: Build prompt and call LLM
            decisions_context = self._format_decisions_for_prompt(relevant_decisions + linked_decisions)
            prompt = WHY_DID_WE_PROMPT.format(
                question=question,
                decisions_context=decisions_context,
                artifacts_context=artifacts_context_text or "(No additional artifact context available)",
            )
            messages = [
                {"role": "system", "content": "You are a decision intelligence assistant."},
                {"role": "user", "content": prompt},
            ]

            try:
                answer = await self.llm.generate(messages, max_tokens=2048)
            except Exception as e:
                logger.error("LLM failed during why_did_we synthesis: %s", e)
                answer = self._build_fallback_answer(relevant_decisions)

            # Compute a rough confidence based on number of decisions and their scores
            avg_confidence = sum(d.get("confidence_score", 0.5) for d in relevant_decisions) / len(relevant_decisions)

            return {
                "question": question,
                "answer": answer,
                "confidence": round(avg_confidence, 3),
                "decision_trail": relevant_decisions,
                "linked_decisions": linked_decisions,
                "sources": source_artifacts,
                "related_members": related_members,
            }

        except Exception as e:
            logger.error("why_did_we failed: %s", e)
            raise
        finally:
            db.close()

    async def get_decision_timeline(
        self, topic: str, limit: int = 50, organization_id: str | None = None
    ) -> list[dict]:
        """Get chronological timeline of decisions related to a topic."""
        db = create_session()
        try:
            escaped_topic = topic.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped_topic}%"

            query = db.query(DecisionRecord).filter(
                or_(
                    DecisionRecord.title.ilike(pattern),
                    DecisionRecord.description.ilike(pattern),
                    DecisionRecord.context_summary.ilike(pattern),
                )
            )
            if organization_id:
                query = query.filter(DecisionRecord.organization_id == organization_id)

            # Order by decided_at if available, otherwise by created_at
            decisions = (
                query.order_by(
                    DecisionRecord.decided_at.asc().nullslast(),
                    DecisionRecord.created_at.asc(),
                )
                .limit(limit)
                .all()
            )

            timeline = []
            for d in decisions:
                entry = self._decision_to_dict(d)
                entry["effective_date"] = (
                    d.decided_at.isoformat()
                    if d.decided_at
                    else (d.created_at.isoformat() if d.created_at else None)
                )
                timeline.append(entry)

            return timeline

        finally:
            db.close()

    def _decision_to_dict(self, decision: DecisionRecord) -> dict:
        """Convert a DecisionRecord to a serializable dict."""
        return {
            "id": decision.id,
            "title": decision.title,
            "description": decision.description,
            "decision_type": decision.decision_type,
            "status": decision.status,
            "confidence_score": decision.confidence_score,
            "context_summary": decision.context_summary,
            "alternatives_considered": decision.alternatives_considered or [],
            "outcome_summary": decision.outcome_summary,
            "source_artifact_ids": decision.source_artifact_ids or [],
            "source_chunk_ids": decision.source_chunk_ids or [],
            "involved_member_ids": decision.involved_member_ids or [],
            "tags": decision.tags or [],
            "decided_at": decision.decided_at.isoformat() if decision.decided_at else None,
            "extracted_at": decision.extracted_at.isoformat() if decision.extracted_at else None,
            "created_at": decision.created_at.isoformat() if decision.created_at else None,
            "updated_at": decision.updated_at.isoformat() if decision.updated_at else None,
        }

    def _format_decisions_for_prompt(self, decisions: list[dict]) -> str:
        """Format decisions into text for LLM prompt."""
        if not decisions:
            return "(No decisions found)"

        parts = []
        for i, d in enumerate(decisions, 1):
            part = f"Decision {i}: {d['title']}\n"
            if d.get("description"):
                part += f"  Description: {d['description']}\n"
            if d.get("context_summary"):
                part += f"  Context: {d['context_summary']}\n"
            if d.get("alternatives_considered"):
                part += f"  Alternatives considered: {', '.join(d['alternatives_considered'])}\n"
            if d.get("outcome_summary"):
                part += f"  Outcome: {d['outcome_summary']}\n"
            if d.get("decision_type"):
                part += f"  Type: {d['decision_type']}\n"
            if d.get("status"):
                part += f"  Status: {d['status']}\n"
            if d.get("decided_at"):
                part += f"  Date: {d['decided_at']}\n"
            if d.get("tags"):
                part += f"  Tags: {', '.join(d['tags'])}\n"
            parts.append(part)

        return "\n".join(parts)

    def _build_fallback_answer(self, decisions: list[dict]) -> str:
        """Build a simple answer when LLM is unavailable."""
        if not decisions:
            return "No relevant decisions found."

        parts = ["Based on the team's decision records, here are the relevant decisions:\n"]
        for d in decisions:
            parts.append(f"- **{d['title']}**")
            if d.get("context_summary"):
                parts.append(f"  Context: {d['context_summary']}")
            if d.get("alternatives_considered"):
                parts.append(f"  Alternatives: {', '.join(d['alternatives_considered'])}")
            parts.append("")

        return "\n".join(parts)

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)
