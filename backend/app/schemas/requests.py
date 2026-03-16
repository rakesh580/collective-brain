from pydantic import BaseModel, EmailStr, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None
    filters: dict | None = None
    room_id: str | None = None


class GitIngestRequest(BaseModel):
    repo_path: str = Field(..., min_length=1, max_length=500)
    branch: str = "main"
    since_days: int = Field(90, ge=1, le=365)
    room_id: str | None = None


class MarkdownIngestRequest(BaseModel):
    directory_path: str = Field(..., min_length=1, max_length=500)
    room_id: str | None = None


class MemberAliasUpdate(BaseModel):
    aliases: list[str] = Field(..., max_length=50)


class MemberCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: str | None = Field(None, max_length=200)
    expertise_tags: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


class MemberUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    email: str | None = None
    expertise_tags: list[str] | None = None
    strengths: list[str] | None = None
    weaknesses: list[str] | None = None


# Auth
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9@._-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    display_name: str | None = Field(None, max_length=100)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., min_length=1, description="Google ID token (JWT)")


class GoogleAccessTokenRequest(BaseModel):
    access_token: str = Field(..., min_length=1, description="Google OAuth2 access token")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=8, max_length=8)
    new_password: str = Field(..., min_length=8, max_length=100)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    avatar_url: str | None = Field(None, max_length=500)
    linked_member_id: str | None = None
    skills: list[str] | None = None
    role_title: str | None = Field(None, max_length=200)
    bio: str | None = Field(None, max_length=1000)


# Conversations
class ShareConversationRequest(BaseModel):
    user_ids: list[str] = Field(..., min_length=1)


# Discussions
class CreateThreadRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    context_type: str | None = Field(None, pattern=r"^(member|insight)$")
    context_id: str | None = None
    room_id: str | None = None


class CreateDiscussionMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    parent_message_id: str | None = None


class EditDiscussionMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


# Rooms
class CreateRoomRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    member_user_ids: list[str] = Field(default_factory=list)
    is_public: bool = Field(default=False)


class UpdateRoomRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    is_public: bool | None = None


class AddRoomMembersRequest(BaseModel):
    user_ids: list[str] = Field(..., min_length=1)


class RoomMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    parent_message_id: str | None = None


class RoomAIQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
