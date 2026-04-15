import asyncio
import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.contribution import ContributionRecord
from app.models.conversation import ConversationRecord, MessageRecord
from app.models.member import MemberRecord
from app.models.user import UserRecord
from app.schemas.responses import QueryResponse, RelatedMember, SourceRef
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.prompts import (
    CONTEXT_TEMPLATE,
    MEMBER_RECOMMENDATION_TEMPLATE,
    PATTERN_ANALYSIS_TEMPLATE,
    STRATEGY_TEMPLATE,
    SYSTEM_PROMPT,
)
from app.services.vector_store import VectorStoreService

logger = logging.getLogger("collective_brain.rag")

LLM_TIMEOUT_SECONDS = 90
FALLBACK_RESPONSE = (
    "I'm sorry, the AI service is temporarily unavailable or took too long to respond. Please try again in a moment."
)


class RAGPipeline:
    def __init__(
        self,
        llm: LLMService,
        embedder: EmbeddingService,
        vector_store: VectorStoreService,
        db: Session,
    ):
        self.llm = llm
        self.embedder = embedder
        self.vs = vector_store
        self.db = db

    async def answer(
        self,
        question: str,
        conversation_id: str | None = None,
        filters: dict | None = None,
        sender_user_id: str | None = None,
        sender_name: str | None = None,
        room_id: str | None = None,
    ) -> QueryResponse:
        self.room_id = room_id

        # Step 1: Classify intent
        intent = self._classify_intent(question)

        # Step 2: Retrieve relevant chunks
        query_embedding = self.embedder.embed(question)
        where_filter = self._build_chroma_filter(filters)
        results = self.vs.query(
            query_embedding=query_embedding,
            n_results=8,
            where=where_filter,
            room_id=room_id,
        )

        # Step 3: Build context based on intent
        chunks_text = self._format_chunks(results)
        user_content = self._build_context(intent, question, chunks_text)

        # Step 4: Get or create conversation, build messages with DB history
        conv_id = conversation_id or str(uuid4())
        self._ensure_conversation(conv_id, question, sender_user_id)
        messages = self._build_messages(conv_id, user_content)

        # Step 5: Call LLM with timeout
        try:
            response_text = await asyncio.wait_for(
                self.llm.generate(messages),
                timeout=LLM_TIMEOUT_SECONDS,
            )
        except (TimeoutError, Exception) as e:
            logger.error("LLM call failed: %s", e)
            response_text = FALLBACK_RESPONSE

        # Step 6: Persist messages to database
        self._save_messages(conv_id, user_content, response_text, results, sender_user_id, sender_name)

        # Step 7: Build response
        sources = self._format_sources(results)
        related_members = self._extract_related_members(response_text)

        return QueryResponse(
            answer=response_text,
            sources=sources,
            related_members=related_members,
            conversation_id=conv_id,
        )

    def _ensure_conversation(self, conv_id: str, question: str, owner_user_id: str | None = None):
        existing = self.db.query(ConversationRecord).filter(ConversationRecord.id == conv_id).first()
        if not existing:
            conv = ConversationRecord(
                id=conv_id,
                title=(question.strip()[:100] or "Untitled"),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                owner_user_id=owner_user_id,
                room_id=getattr(self, "room_id", None),
            )
            self.db.add(conv)
            self.db.commit()

    def _save_messages(
        self,
        conv_id: str,
        user_content: str,
        response_text: str,
        results: dict,
        sender_user_id: str | None = None,
        sender_name: str | None = None,
    ):
        now = datetime.now(UTC)
        user_msg = MessageRecord(
            id=str(uuid4()),
            conversation_id=conv_id,
            role="user",
            content=user_content,
            created_at=now,
            sender_user_id=sender_user_id,
            sender_name=sender_name,
        )

        sources_data = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        for chunk_id, doc, meta, dist in zip(ids, docs, metadatas, distances):
            sources_data.append(
                {
                    "chunk_id": chunk_id,
                    "text": doc[:300],
                    "source_type": meta.get("source_type", "unknown"),
                    "source_ref": meta.get("source_ref", ""),
                    "score": round(1 - dist, 3),
                }
            )

        related = self._extract_related_members(response_text)
        related_data = [{"id": r.id, "name": r.name, "relevance": r.relevance} for r in related]

        assistant_msg = MessageRecord(
            id=str(uuid4()),
            conversation_id=conv_id,
            role="assistant",
            content=response_text,
            sources=sources_data,
            related_members=related_data,
            created_at=now,
        )
        self.db.add(user_msg)
        self.db.add(assistant_msg)

        conv = self.db.query(ConversationRecord).filter(ConversationRecord.id == conv_id).first()
        if conv:
            conv.updated_at = now
            msg_count = self.db.query(MessageRecord).filter(MessageRecord.conversation_id == conv_id).count()
            conv.message_count = msg_count + 2

        self.db.commit()

    def _classify_intent(self, question: str) -> str:
        q = question.lower()
        if any(w in q for w in ["who should", "best person", "who can", "assign", "who knows"]):
            return "member_recommendation"
        if any(w in q for w in ["pattern", "keep causing", "recurring", "why do we", "bottleneck"]):
            return "pattern_analysis"
        if any(
            w in q
            for w in [
                "strategy",
                "plan",
                "weekly",
                "next week",
                "priorities",
                "recommend",
            ]
        ):
            return "strategy_generation"
        return "general"

    def _build_chroma_filter(self, filters: dict | None) -> dict | None:
        if not filters:
            return None
        conditions = []
        if "source_types" in filters and filters["source_types"]:
            conditions.append({"source_type": {"$in": filters["source_types"]}})
        if "members" in filters and filters["members"]:
            conditions.append({"author": {"$in": filters["members"]}})
        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def _format_chunks(self, results: dict) -> str:
        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        parts = []
        for doc, meta in zip(docs, metadatas):
            source = meta.get("source_type", "unknown")
            ref = meta.get("source_ref", "")
            author = meta.get("author", "unknown")
            parts.append(f"[{source}] ({author}) {ref}\n{doc}")
        return "\n\n---\n\n".join(parts) if parts else "(No relevant context found)"

    def _build_context(self, intent: str, question: str, chunks_text: str) -> str:
        if intent == "member_recommendation":
            member_expertise = self._get_member_expertise_summary()
            user_skills = self._get_user_skills_summary()
            return MEMBER_RECOMMENDATION_TEMPLATE.format(
                chunks=chunks_text,
                member_expertise=member_expertise,
                user_skills=user_skills,
                question=question,
            )
        if intent == "pattern_analysis":
            contributions = self._get_recent_contributions_summary()
            return PATTERN_ANALYSIS_TEMPLATE.format(
                chunks=chunks_text,
                contributions=contributions,
                question=question,
            )
        if intent == "strategy_generation":
            activity = self._get_recent_contributions_summary()
            return STRATEGY_TEMPLATE.format(
                chunks=chunks_text,
                activity_summary=activity,
                task_status="(see context above)",
                question=question,
            )
        # General queries — include user skills summary for team awareness
        user_skills = self._get_user_skills_summary()
        context = CONTEXT_TEMPLATE.format(chunks=chunks_text, question=question)
        if user_skills and user_skills != "(No user skill profiles yet)":
            context = context.replace(
                "=== QUESTION ===", f"=== TEAM SKILL PROFILES ===\n{user_skills}\n\n=== QUESTION ==="
            )
        return context

    def _build_messages(self, conv_id: str, user_content: str) -> list[dict]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        # Load only the last 6 messages using SQL (not all + Python slice)
        history = (
            self.db.query(MessageRecord)
            .filter(MessageRecord.conversation_id == conv_id)
            .order_by(MessageRecord.created_at.desc())
            .limit(6)
            .all()
        )
        # Reverse to chronological order
        history.reverse()
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_content})
        return messages

    def _format_sources(self, results: dict) -> list[SourceRef]:
        sources = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        for chunk_id, doc, meta, dist in zip(ids, docs, metadatas, distances):
            sources.append(
                SourceRef(
                    chunk_id=chunk_id,
                    text=doc[:300],
                    source_type=meta.get("source_type", "unknown"),
                    source_ref=meta.get("source_ref", ""),
                    score=round(1 - dist, 3),
                )
            )
        return sources

    def _extract_related_members(self, response_text: str) -> list[RelatedMember]:
        # Only load members relevant to the current context (room or limited set)
        room_id = getattr(self, "room_id", None)
        if room_id:
            member_ids = (
                self.db.query(ContributionRecord.member_id)
                .filter(ContributionRecord.room_id == room_id)
                .distinct()
                .all()
            )
            mid_list = [mid for (mid,) in member_ids if mid]
            members = (self.db.query(MemberRecord).filter(MemberRecord.id.in_(mid_list)).all()) if mid_list else []
        else:
            # Limit to active members (those with contributions)
            members = self.db.query(MemberRecord).filter(MemberRecord.total_contributions > 0).limit(100).all()
        mentioned = []
        response_lower = response_text.lower()
        for m in members:
            if m.name.lower() in response_lower:
                mentioned.append(RelatedMember(id=m.id, name=m.name, relevance="mentioned in answer"))
        return mentioned

    def _get_member_expertise_summary(self) -> str:
        room_id = getattr(self, "room_id", None)
        if room_id:
            member_ids = (
                self.db.query(ContributionRecord.member_id)
                .filter(ContributionRecord.room_id == room_id)
                .distinct()
                .all()
            )
            member_id_list = [mid for (mid,) in member_ids]
            members = (
                self.db.query(MemberRecord).filter(MemberRecord.id.in_(member_id_list)).all() if member_id_list else []
            )
        else:
            members = self.db.query(MemberRecord).all()
        if not members:
            return "(No members tracked yet)"
        parts = []
        for m in members:
            tags = ", ".join(m.expertise_tags or [])
            scores = m.expertise_scores or {}
            score_str = ", ".join(f"{k}: {v:.2f}" for k, v in scores.items())
            # Include declared skills from linked user
            linked_user = self.db.query(UserRecord).filter(UserRecord.linked_member_id == m.id).first()
            declared = ""
            role = ""
            if linked_user:
                declared = ", ".join(linked_user.skills or [])
                role = linked_user.role_title or ""
            role_str = f" ({role})" if role else ""
            declared_str = f", declared_skills=[{declared}]" if declared else ""
            parts.append(f"- {m.name}{role_str}: tags=[{tags}], scores=[{score_str}]{declared_str}")
        return "\n".join(parts)

    def _get_user_skills_summary(self) -> str:
        """Get declared skills for all users (including those not linked to members)."""
        room_id = getattr(self, "room_id", None)
        if room_id:
            from app.models.room import ChatRoomMember

            user_ids = self.db.query(ChatRoomMember.user_id).filter(ChatRoomMember.room_id == room_id).all()
            uid_list = [uid for (uid,) in user_ids]
            users = self.db.query(UserRecord).filter(UserRecord.id.in_(uid_list)).all() if uid_list else []
        else:
            users = self.db.query(UserRecord).filter(UserRecord.is_active == True).all()  # noqa: E712
        parts = []
        for u in users:
            skills = u.skills or []
            if not skills and not u.role_title:
                continue
            name = u.display_name or u.username
            role = f" ({u.role_title})" if u.role_title else ""
            skill_str = ", ".join(skills) if skills else "none declared"
            parts.append(f"- {name}{role}: skills=[{skill_str}]")
        return "\n".join(parts) if parts else "(No user skill profiles yet)"

    def _get_recent_contributions_summary(self) -> str:
        room_id = getattr(self, "room_id", None)
        query = self.db.query(ContributionRecord)
        if room_id:
            query = query.filter(ContributionRecord.room_id == room_id)
        contribs = query.order_by(ContributionRecord.timestamp.desc()).limit(20).all()
        if not contribs:
            return "(No contributions tracked yet)"
        parts = []
        for c in contribs:
            parts.append(f"- [{c.contribution_type}] {c.description} (by {c.member_id}, {c.timestamp})")
        return "\n".join(parts)
