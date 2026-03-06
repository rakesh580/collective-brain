"""
LangGraph ReAct agent pipeline for the Collective Brain.

Replaces the keyword-based RAG pipeline with an autonomous agent
that reasons about which tools to use and synthesizes multi-step results.
"""

import logging
from datetime import datetime
from uuid import uuid4

from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.conversation import ConversationRecord, MessageRecord
from app.models.member import MemberRecord
from app.schemas.responses import QueryResponse, SourceRef, RelatedMember
from app.services.agent_tools import create_tools
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStoreService

logger = logging.getLogger("collective_brain.agent")

AGENT_SYSTEM_PROMPT = """You are the "Collective Brain" — an intelligent agent for a team. You have access to tools that let you search the team's knowledge base, look up member profiles, find experts, analyze collaboration patterns, and more. You also have access to user-declared skill profiles alongside computed expertise from contributions.

Your role:
- Answer questions about the team's knowledge, activities, and patterns
- Recommend team members based on BOTH their self-declared skills AND demonstrated expertise from contributions
- Identify recurring patterns, bottlenecks, and risks
- Generate strategic recommendations grounded in actual team data

How to work:
- Use your tools to gather information before answering. Don't guess — look it up.
- For "who should handle X?" questions: use find_experts and get_member_profile. These tools include both declared skills and computed expertise.
- For pattern/risk questions: use analyze_patterns and get_recent_activity to find real data.
- For strategy questions: combine get_weekly_summary, get_recent_activity, and analyze_patterns.
- Always cite specific evidence from tool results.
- If the tools don't return enough info, say so honestly.
- Reference team members by name.

Formatting:
- Use **markdown**: **bold** for emphasis, bullet points for lists, ### headers for sections, `code` for technical terms.
- Structure responses with clear sections and bullet points.
- Be conversational yet precise."""


class AgentPipeline:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        embedder: EmbeddingService,
        vector_store: VectorStoreService,
    ):
        self.db = db
        self.settings = settings
        self.embedder = embedder
        self.vector_store = vector_store

        # Initialize LLM via HuggingFace's OpenAI-compatible Router API
        self.llm = ChatOpenAI(
            model=settings.mistral_model,
            api_key=settings.effective_mistral_api_key,
            base_url="https://router.huggingface.co/v1/",
            temperature=0.1,
        )

        # Default tools (no room scope) — will be recreated per-query if room_id is provided
        self.tools = create_tools(db, embedder, vector_store)
        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=AGENT_SYSTEM_PROMPT,
        )

    async def answer(
        self,
        question: str,
        conversation_id: str | None = None,
        filters: dict | None = None,
        sender_user_id: str | None = None,
        sender_name: str | None = None,
        room_id: str | None = None,
    ) -> QueryResponse:
        """Run the agent to answer a question."""
        self._room_id = room_id
        # Recreate tools with room scope if provided
        if room_id:
            self.tools = create_tools(self.db, self.embedder, self.vector_store, room_id=room_id)
            self.agent = create_react_agent(
                model=self.llm,
                tools=self.tools,
                prompt=AGENT_SYSTEM_PROMPT,
            )

        # Ensure conversation exists
        conversation_id = self._ensure_conversation(question, conversation_id, sender_user_id)

        # Build message history from DB
        history = self._load_history(conversation_id)

        # Build input messages
        messages = history + [HumanMessage(content=question)]

        # Run the agent with iteration limit
        try:
            result = await self.agent.ainvoke(
                {"messages": messages},
                config={"recursion_limit": self.settings.agent_max_iterations * 2},
            )

            # Extract the final answer
            final_messages = result.get("messages", [])
            answer_text = ""
            tool_calls_made = []

            for msg in final_messages:
                if isinstance(msg, AIMessage):
                    if msg.content:
                        answer_text = msg.content
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        tool_calls_made.extend(msg.tool_calls)

            if not answer_text:
                answer_text = "I wasn't able to generate a response. Please try rephrasing your question."

        except Exception as e:
            logger.error("Agent execution failed: %s", e, exc_info=True)
            answer_text = f"I encountered an error while processing your question. Please try again. (Error: {type(e).__name__})"
            tool_calls_made = []

        # Extract sources from tool calls
        sources = self._extract_sources(tool_calls_made)

        # Extract related members from the answer
        related_members = self._extract_related_members(answer_text)

        # Save messages to DB
        self._save_messages(conversation_id, question, answer_text, sources, related_members, sender_user_id, sender_name)

        return QueryResponse(
            answer=answer_text,
            sources=sources,
            related_members=related_members,
            conversation_id=conversation_id,
        )

    def _ensure_conversation(self, question: str, conversation_id: str | None, owner_user_id: str | None = None) -> str:
        """Create or retrieve a conversation record."""
        if conversation_id:
            conv = (
                self.db.query(ConversationRecord)
                .filter(ConversationRecord.id == conversation_id)
                .first()
            )
            if conv:
                return conversation_id

        # Create new conversation
        conv_id = str(uuid4())
        title = question.strip()[:100] or "Untitled"
        conv = ConversationRecord(
            id=conv_id,
            title=title,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message_count=0,
            owner_user_id=owner_user_id,
            room_id=getattr(self, "_room_id", None),
        )
        self.db.add(conv)
        self.db.commit()
        return conv_id

    def _load_history(self, conversation_id: str) -> list:
        """Load conversation history as LangChain messages."""
        db_messages = (
            self.db.query(MessageRecord)
            .filter(MessageRecord.conversation_id == conversation_id)
            .order_by(MessageRecord.created_at.asc())
            .all()
        )

        # Keep last 6 messages for context
        recent = db_messages[-6:] if len(db_messages) > 6 else db_messages

        messages = []
        for m in recent:
            if m.role == "user":
                messages.append(HumanMessage(content=m.content))
            elif m.role == "assistant":
                messages.append(AIMessage(content=m.content))

        return messages

    def _save_messages(
        self,
        conversation_id: str,
        question: str,
        answer: str,
        sources: list[SourceRef],
        related_members: list[RelatedMember],
        sender_user_id: str | None = None,
        sender_name: str | None = None,
    ):
        """Save the user question and agent response to DB."""
        now = datetime.utcnow()

        # Save user message
        user_msg = MessageRecord(
            id=str(uuid4()),
            conversation_id=conversation_id,
            role="user",
            content=question,
            created_at=now,
            sender_user_id=sender_user_id,
            sender_name=sender_name,
        )
        self.db.add(user_msg)

        # Save assistant message
        assistant_msg = MessageRecord(
            id=str(uuid4()),
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            sources=[s.model_dump() for s in sources],
            related_members=[rm.model_dump() for rm in related_members],
            created_at=now,
        )
        self.db.add(assistant_msg)

        # Update conversation
        conv = (
            self.db.query(ConversationRecord)
            .filter(ConversationRecord.id == conversation_id)
            .first()
        )
        if conv:
            msg_count = (
                self.db.query(MessageRecord)
                .filter(MessageRecord.conversation_id == conversation_id)
                .count()
            )
            conv.message_count = msg_count
            conv.updated_at = now

        self.db.commit()

    def _extract_sources(self, tool_calls: list) -> list[SourceRef]:
        """Extract source references from the tools that were called."""
        sources = []
        for tc in tool_calls:
            tool_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
            args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})

            # Only search_knowledge returns actual source documents
            if tool_name == "search_knowledge":
                query = args.get("query", "")
                sources.append(
                    SourceRef(
                        chunk_id=f"agent-search-{uuid4().hex[:8]}",
                        text=f"Agent searched: '{query}'",
                        source_type="agent_search",
                        source_ref=query,
                        score=1.0,
                    )
                )
            elif tool_name:
                sources.append(
                    SourceRef(
                        chunk_id=f"agent-tool-{uuid4().hex[:8]}",
                        text=f"Agent used tool: {tool_name}({', '.join(f'{k}={v}' for k, v in args.items())})",
                        source_type="agent_tool",
                        source_ref=tool_name,
                        score=0.9,
                    )
                )
        return sources

    def _extract_related_members(self, response_text: str) -> list[RelatedMember]:
        """Find team members mentioned in the response."""
        members = self.db.query(MemberRecord).all()
        related = []
        seen = set()

        for m in members:
            if m.name.lower() in response_text.lower() and m.id not in seen:
                related.append(
                    RelatedMember(
                        id=m.id,
                        name=m.name,
                        relevance="mentioned in response",
                    )
                )
                seen.add(m.id)

        return related
