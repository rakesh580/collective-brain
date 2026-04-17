import json
import logging
import uuid
from datetime import UTC, datetime

from app.db.database import create_session
from app.models.artifact import ArtifactRecord
from app.models.decision import DecisionLink, DecisionRecord
from app.models.knowledge_embedding import KnowledgeEmbedding
from app.services.llm_service import LLMService

logger = logging.getLogger("collective_brain.decisions.extraction")

EXTRACTION_PROMPT_TEMPLATE = """You are an expert at analyzing team documents and extracting decisions.

Analyze the following text from a team artifact and extract ALL decisions that were made.
A decision is any choice, resolution, agreement, or conclusion that the team arrived at.

For each decision found, provide the following in a JSON array:

[
  {{
    "title": "Short descriptive title (e.g. 'Chose PostgreSQL over MongoDB for billing service')",
    "description": "Full description of the decision and what was decided",
    "context_summary": "Why this decision was made - the reasoning, constraints, and factors",
    "alternatives_considered": ["Alternative 1", "Alternative 2"],
    "involved_people": ["Person Name 1", "Person Name 2"],
    "tags": ["topic1", "topic2"],
    "approximate_date": "YYYY-MM-DD or null if unknown",
    "decision_type": "technical|architectural|process|strategic",
    "confidence": 0.85
  }}
]

Rules:
- Only extract actual decisions, not discussions or proposals that weren't resolved
- The confidence field (0-1) indicates how certain you are this is a real decision
- If no decisions are found, return an empty array: []
- Return ONLY valid JSON, no other text
- Each title should be specific and actionable, not vague

TEXT TO ANALYZE:
---
{text}
---

Return ONLY the JSON array:"""


class DecisionExtractionService:
    """Extracts decisions from ingested artifacts using LLM."""

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def extract_decisions_from_artifact(self, artifact_id: str) -> list[dict]:
        """Read chunks from an artifact, send to LLM with a prompt asking to extract decisions.
        Return list of extracted decisions with title, description, context, alternatives, involved people, tags."""
        db = create_session()
        try:
            artifact = db.query(ArtifactRecord).filter(ArtifactRecord.id == artifact_id).first()
            if not artifact:
                logger.warning("Artifact %s not found for decision extraction", artifact_id)
                return []

            # Get chunks for this artifact
            chunks = (
                db.query(KnowledgeEmbedding)
                .filter(KnowledgeEmbedding.artifact_id == artifact_id)
                .order_by(KnowledgeEmbedding.created_at.asc())
                .all()
            )

            if not chunks:
                logger.info("No chunks found for artifact %s, skipping extraction", artifact_id)
                return []

            # Combine chunk texts (limit to avoid token overflow)
            chunk_texts = []
            chunk_ids = []
            total_chars = 0
            max_chars = 12000  # ~3000 tokens

            for chunk in chunks:
                if total_chars + len(chunk.content) > max_chars:
                    break
                chunk_texts.append(chunk.content)
                chunk_ids.append(chunk.id)
                total_chars += len(chunk.content)

            combined_text = "\n\n---\n\n".join(chunk_texts)

            # Build prompt and call LLM
            prompt = self._build_extraction_prompt(combined_text)
            messages = [
                {"role": "system", "content": "You are a decision extraction assistant. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ]

            try:
                raw_response = await self.llm.generate(messages, max_tokens=4096)
            except Exception as e:
                logger.error("LLM failed during decision extraction for artifact %s: %s", artifact_id, e)
                return []

            # Parse response
            extracted = self._parse_llm_response(raw_response)
            if not extracted:
                logger.info("No decisions extracted from artifact %s", artifact_id)
                return []

            # Save decisions to DB
            saved_decisions = []
            for item in extracted:
                decision_id = str(uuid.uuid4())
                decided_at = None
                if item.get("approximate_date"):
                    try:
                        decided_at = datetime.strptime(item["approximate_date"], "%Y-%m-%d").replace(tzinfo=UTC)
                    except (ValueError, TypeError):
                        decided_at = None

                decision = DecisionRecord(
                    id=decision_id,
                    organization_id=artifact.organization_id,
                    title=item.get("title", "Untitled Decision"),
                    description=item.get("description"),
                    decision_type=item.get("decision_type", "technical"),
                    status="active",
                    confidence_score=float(item.get("confidence", 0.5)),
                    context_summary=item.get("context_summary"),
                    alternatives_considered=item.get("alternatives_considered", []),
                    outcome_summary=None,
                    source_artifact_ids=[artifact_id],
                    source_chunk_ids=chunk_ids,
                    involved_member_ids=[],
                    tags=item.get("tags", []),
                    decided_at=decided_at,
                    extracted_at=datetime.now(UTC),
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                db.add(decision)
                saved_decisions.append(
                    {
                        "id": decision_id,
                        "title": decision.title,
                        "description": decision.description,
                        "decision_type": decision.decision_type,
                        "confidence_score": decision.confidence_score,
                        "context_summary": decision.context_summary,
                        "alternatives_considered": decision.alternatives_considered,
                        "tags": decision.tags,
                        "decided_at": decided_at.isoformat() if decided_at else None,
                        "source_artifact_ids": decision.source_artifact_ids,
                    }
                )

            db.commit()
            logger.info(
                "Extracted %d decisions from artifact %s",
                len(saved_decisions),
                artifact_id,
            )
            return saved_decisions

        except Exception as e:
            db.rollback()
            logger.error("Decision extraction failed for artifact %s: %s", artifact_id, e)
            raise
        finally:
            db.close()

    async def extract_decisions_bulk(self, artifact_ids: list[str]) -> dict:
        """Extract decisions from multiple artifacts."""
        results = {
            "total_artifacts": len(artifact_ids),
            "processed": 0,
            "total_decisions": 0,
            "decisions_by_artifact": {},
            "errors": [],
        }

        for artifact_id in artifact_ids:
            try:
                decisions = await self.extract_decisions_from_artifact(artifact_id)
                results["processed"] += 1
                results["total_decisions"] += len(decisions)
                results["decisions_by_artifact"][artifact_id] = decisions
            except Exception as e:
                logger.error("Bulk extraction failed for artifact %s: %s", artifact_id, e)
                results["errors"].append({"artifact_id": artifact_id, "error": str(e)})

        return results

    async def link_related_decisions(self, decision_id: str, embedding_service=None, vector_store=None) -> list[dict]:
        """Use embeddings to find related decisions and create links."""
        db = create_session()
        try:
            decision = db.query(DecisionRecord).filter(DecisionRecord.id == decision_id).first()
            if not decision:
                logger.warning("Decision %s not found for linking", decision_id)
                return []

            if not embedding_service or not vector_store:
                logger.warning("Embedding service or vector store not available for linking")
                return []

            # Embed the decision text
            text_to_embed = f"{decision.title}. {decision.description or ''} {decision.context_summary or ''}"
            query_embedding = embedding_service.embed(text_to_embed)

            # Find all other decisions
            all_decisions = db.query(DecisionRecord).filter(DecisionRecord.id != decision_id).all()

            if not all_decisions:
                return []

            # Compute similarities
            links_created = []
            for other in all_decisions:
                other_text = f"{other.title}. {other.description or ''} {other.context_summary or ''}"
                other_embedding = embedding_service.embed(other_text)

                # Cosine similarity
                similarity = self._cosine_similarity(query_embedding, other_embedding)

                if similarity > 0.7:  # threshold for "related"
                    # Check if link already exists
                    existing = (
                        db.query(DecisionLink)
                        .filter(
                            DecisionLink.from_decision_id == decision_id,
                            DecisionLink.to_decision_id == other.id,
                        )
                        .first()
                    )
                    if not existing:
                        link_id = str(uuid.uuid4())
                        link = DecisionLink(
                            id=link_id,
                            from_decision_id=decision_id,
                            to_decision_id=other.id,
                            link_type="related",
                            created_at=datetime.now(UTC),
                        )
                        db.add(link)
                        links_created.append(
                            {
                                "id": link_id,
                                "from_decision_id": decision_id,
                                "to_decision_id": other.id,
                                "to_decision_title": other.title,
                                "link_type": "related",
                                "similarity": round(similarity, 3),
                            }
                        )

            db.commit()
            logger.info("Created %d links for decision %s", len(links_created), decision_id)
            return links_created

        except Exception as e:
            db.rollback()
            logger.error("Decision linking failed for %s: %s", decision_id, e)
            raise
        finally:
            db.close()

    def _build_extraction_prompt(self, chunks_text: str) -> str:
        """Build the LLM prompt for decision extraction."""
        return EXTRACTION_PROMPT_TEMPLATE.format(text=chunks_text)

    def _parse_llm_response(self, raw_response: str) -> list[dict]:
        """Parse LLM JSON response into a list of decision dicts."""
        # Try to extract JSON from the response
        text = raw_response.strip()

        # Remove markdown code block markers if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict) and "decisions" in parsed:
                return parsed["decisions"]
            logger.warning("LLM response was valid JSON but unexpected structure: %s", type(parsed))
            return []
        except json.JSONDecodeError:
            # Try to find JSON array in the text
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
            logger.warning("Failed to parse LLM response as JSON: %s", text[:200])
            return []

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)
