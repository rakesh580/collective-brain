from pydantic import BaseModel, field_validator
from datetime import datetime


class SourceRef(BaseModel):
    chunk_id: str
    text: str
    source_type: str
    source_ref: str
    score: float


class RelatedMember(BaseModel):
    id: str
    name: str
    relevance: str = ""


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceRef] = []
    related_members: list[RelatedMember] = []
    conversation_id: str


class IngestionResponse(BaseModel):
    artifact_id: str
    source_type: str
    status: str
    chunk_count: int
    member_count: int


class MemberResponse(BaseModel):
    id: str
    name: str
    aliases: list[str]
    email: str | None
    expertise_tags: list[str]
    expertise_scores: dict[str, float]
    strengths: list[str]
    weaknesses: list[str]
    last_active: datetime
    total_contributions: float

    model_config = {"from_attributes": True}


class MemberDetailResponse(MemberResponse):
    contributions: list["ContributionResponse"] = []


class ContributionResponse(BaseModel):
    id: str
    contribution_type: str
    timestamp: datetime
    description: str
    topics: list[str]

    model_config = {"from_attributes": True}


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    properties: dict = {}
    size: float = 1.0


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    weight: float = 1.0
    label: str = ""


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class InsightResponse(BaseModel):
    id: str
    insight_type: str
    title: str
    body: str
    generated_at: datetime
    related_member_ids: list[str]
    confidence: float

    model_config = {"from_attributes": True}


class DashboardResponse(BaseModel):
    total_members: int
    total_artifacts: int
    total_chunks: int
    top_insights: list[InsightResponse]
    active_members: list[MemberResponse]


class WeeklySummaryResponse(BaseModel):
    summary: str
    period_start: datetime
    period_end: datetime
    highlights: list[str]
    recommendations: list[str]


class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    llm_available: bool
    vector_store_count: int
    embedding_model: str
    agent_mode: str = "rag"


# Auth
class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    display_name: str | None
    avatar_url: str | None
    linked_member_id: str | None
    is_active: bool
    created_at: datetime
    auth_provider: str | None = None
    role: str = "member"
    skills: list[str] = []
    role_title: str | None = None
    bio: str | None = None

    @field_validator("skills", mode="before")
    @classmethod
    def _coerce_skills(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    token: str
    refresh_token: str
    user: UserResponse


# Conversation sharing
class ParticipantResponse(BaseModel):
    user_id: str
    username: str
    display_name: str | None
    role: str
    joined_at: datetime | None

    model_config = {"from_attributes": True}


# Discussions
class DiscussionMessageResponse(BaseModel):
    id: str
    thread_id: str
    user_id: str
    username: str
    display_name: str | None
    content: str
    created_at: datetime
    edited_at: datetime | None
    parent_message_id: str | None


class DiscussionThreadResponse(BaseModel):
    id: str
    title: str
    created_by_user_id: str
    created_by_username: str
    created_by_display_name: str | None
    status: str
    context_type: str | None
    context_id: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime


class DiscussionThreadDetailResponse(DiscussionThreadResponse):
    messages: list[DiscussionMessageResponse] = []


# Rooms
class RoomMemberResponse(BaseModel):
    user_id: str
    username: str
    display_name: str | None
    role: str
    joined_at: datetime
    is_online: bool = False
    skills: list[str] = []
    role_title: str | None = None

    @field_validator("skills", mode="before")
    @classmethod
    def _coerce_skills(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v


class RoomMessageResponse(BaseModel):
    id: str
    room_id: str
    user_id: str | None
    sender_name: str
    message_type: str  # "user", "ai", "system"
    content: str
    sources: list[SourceRef] = []
    related_members: list[RelatedMember] = []
    created_at: datetime
    edited_at: datetime | None
    parent_message_id: str | None


class RoomResponse(BaseModel):
    id: str
    name: str
    description: str | None
    created_by_user_id: str
    created_by_username: str
    avatar_color: str
    member_count: int
    message_count: int
    last_message_at: datetime | None
    last_message_preview: str | None = None
    created_at: datetime


class RoomDetailResponse(RoomResponse):
    members: list[RoomMemberResponse] = []
    messages: list[RoomMessageResponse] = []
