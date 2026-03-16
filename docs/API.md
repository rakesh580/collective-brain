# Collective Brain REST API Documentation

**Base URL:** `/api`
**Version:** 1.0
**Last Updated:** 2026-03-15

---

## Table of Contents

- [Authentication](#authentication)
- [Error Responses](#error-responses)
- [Rate Limiting](#rate-limiting)
- [WebSocket Protocol](#websocket-protocol)
- [Endpoints](#endpoints)
  - [Health](#health)
  - [Auth (`/api/auth`)](#auth-apiauth)
  - [Query (`/api`)](#query-api)
  - [Members (`/api/members`)](#members-apimembers)
  - [Ingest (`/api/ingest`)](#ingest-apiingest)
  - [Rooms (`/api/rooms`)](#rooms-apirooms)
  - [Conversations (`/api/conversations`)](#conversations-apiconversations)
  - [Discussions (`/api/discussions`)](#discussions-apidiscussions)
  - [Insights (`/api/insights`)](#insights-apiinsights)
  - [Graph (`/api/graph`)](#graph-apigraph)
  - [Analytics (`/api/analytics`)](#analytics-apianalytics)
  - [Artifacts (`/api/artifacts`)](#artifacts-apiartifacts)
  - [Search (`/api/search`)](#search-apisearch)
  - [Slack Integration (`/api/slack`)](#slack-integration-apislack)
  - [GitHub Integration (`/api/github`)](#github-integration-apigithub)
  - [Expert Routing (`/api/experts`)](#expert-routing-apiexperts)

---

## Authentication

Most endpoints require a valid JWT Bearer token. Obtain a token by registering or logging in via the Auth endpoints.

Include the token in every authenticated request using the `Authorization` header:

```
Authorization: Bearer <your_jwt_token>
```

Tokens are returned in the response body of `/api/auth/register`, `/api/auth/login`, and `/api/auth/google`.

If a token is missing, expired, or invalid the API responds with `401 Unauthorized`.

---

## Error Responses

All errors follow a consistent JSON structure:

```json
{
  "detail": "A human-readable error message describing what went wrong."
}
```

### Common HTTP Status Codes

| Code | Meaning |
|------|---------|
| 400  | Bad Request -- invalid or missing parameters |
| 401  | Unauthorized -- missing or invalid JWT token |
| 403  | Forbidden -- insufficient permissions |
| 404  | Not Found -- resource does not exist |
| 409  | Conflict -- resource already exists (e.g., duplicate username) |
| 413  | Payload Too Large -- file exceeds size limit |
| 422  | Unprocessable Entity -- validation error |
| 429  | Too Many Requests -- rate limit exceeded |
| 500  | Internal Server Error |

---

## Rate Limiting

Certain endpoints enforce per-user rate limits. When a limit is exceeded the API returns `429 Too Many Requests` with a `Retry-After` header indicating the number of seconds to wait.

| Endpoint | Limit |
|----------|-------|
| `POST /api/query` | 10 requests per minute |

All other endpoints follow default server-level rate limits.

---

## WebSocket Protocol

Two endpoints expose WebSocket connections: **Rooms** and **Discussions**.

### Connection

1. Open a WebSocket connection to the endpoint (e.g., `ws://<host>/api/rooms/ws/{room_id}`).
2. Immediately send a JSON authentication frame:

```json
{
  "token": "<your_jwt_token>"
}
```

3. The server validates the token. If invalid, the connection is closed.

### Message Types (Client to Server)

| Type | Payload | Description |
|------|---------|-------------|
| `message` | `{"type": "message", "content": "Hello"}` | Send a chat message |
| `typing` | `{"type": "typing"}` | Indicate the user started typing |
| `typing_stop` | `{"type": "typing_stop"}` | Indicate the user stopped typing |
| `ping` | `{"type": "ping"}` | Keep-alive ping |

### Message Types (Server to Client)

The server broadcasts events as JSON frames to all connected clients in the room or thread. Typical fields include `type`, `user_id`, `content`, and `timestamp`.

---

## Endpoints

---

### Health

#### `GET /api/health`

Public health-check endpoint.

- **Auth required:** No

**Response `200 OK`:**

```json
{
  "status": "healthy"
}
```

---

### Auth (`/api/auth`)

#### `GET /api/auth/config`

Return public authentication configuration.

- **Auth required:** No

**Response `200 OK`:**

```json
{
  "google_client_id": "xxxxxxxxxxxx.apps.googleusercontent.com",
  "registration_enabled": true
}
```

---

#### `POST /api/auth/register`

Register a new user account.

- **Auth required:** No

**Request Body:**

```json
{
  "username": "jdoe",
  "email": "jdoe@example.com",
  "password": "securePassword123",
  "display_name": "Jane Doe"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | Yes | Unique username |
| `email` | string | Yes | Valid email address |
| `password` | string | Yes | User password |
| `display_name` | string | No | Display name |

**Response `201 Created`:**

```json
{
  "id": "uuid-string",
  "username": "jdoe",
  "email": "jdoe@example.com",
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Errors:** `409 Conflict` if username or email already exists.

---

#### `POST /api/auth/login`

Authenticate with username and password.

- **Auth required:** No

**Request Body:**

```json
{
  "username": "jdoe",
  "password": "securePassword123"
}
```

| Field | Type | Required |
|-------|------|----------|
| `username` | string | Yes |
| `password` | string | Yes |

**Response `200 OK`:**

```json
{
  "id": "uuid-string",
  "username": "jdoe",
  "email": "jdoe@example.com",
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Errors:** `401 Unauthorized` if credentials are invalid.

---

#### `POST /api/auth/google`

Authenticate using a Google OAuth credential token.

- **Auth required:** No

**Request Body:**

```json
{
  "credential": "google-id-token-string"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `credential` | string | Yes | Google ID token from Google Sign-In |

**Response `200 OK`:**

```json
{
  "id": "uuid-string",
  "username": "jdoe",
  "email": "jdoe@example.com",
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

---

#### `POST /api/auth/forgot-password`

Request a password reset code sent to the user's email.

- **Auth required:** No

**Request Body:**

```json
{
  "email": "jdoe@example.com"
}
```

**Response `200 OK`:**

```json
{
  "message": "If an account with that email exists, a reset code has been sent."
}
```

---

#### `POST /api/auth/reset-password`

Reset password using the code received via email.

- **Auth required:** No

**Request Body:**

```json
{
  "email": "jdoe@example.com",
  "code": "123456",
  "new_password": "newSecurePassword456"
}
```

| Field | Type | Required |
|-------|------|----------|
| `email` | string | Yes |
| `code` | string | Yes |
| `new_password` | string | Yes |

**Response `200 OK`:**

```json
{
  "message": "Password has been reset successfully."
}
```

**Errors:** `400 Bad Request` if the code is invalid or expired.

---

#### `POST /api/auth/change-password`

Change password for the currently authenticated user.

- **Auth required:** Yes

**Request Body:**

```json
{
  "current_password": "oldPassword123",
  "new_password": "newPassword456"
}
```

| Field | Type | Required |
|-------|------|----------|
| `current_password` | string | Yes |
| `new_password` | string | Yes |

**Response `200 OK`:**

```json
{
  "message": "Password changed successfully."
}
```

**Errors:** `401 Unauthorized` if current password is incorrect.

---

#### `GET /api/auth/me`

Get the authenticated user's profile.

- **Auth required:** Yes

**Example Request:**

```bash
curl -H "Authorization: Bearer <token>" https://api.example.com/api/auth/me
```

**Response `200 OK`:**

```json
{
  "id": "uuid-string",
  "username": "jdoe",
  "email": "jdoe@example.com",
  "display_name": "Jane Doe",
  "avatar_url": "https://example.com/avatar.jpg",
  "bio": "Software engineer",
  "skills": ["python", "react"],
  "role_title": "Senior Developer",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

#### `PUT /api/auth/me`

Update the authenticated user's profile.

- **Auth required:** Yes

**Request Body:**

```json
{
  "display_name": "Jane D.",
  "avatar_url": "https://example.com/new-avatar.jpg",
  "bio": "Full-stack engineer",
  "skills": ["python", "react", "typescript"],
  "role_title": "Lead Developer"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `display_name` | string | No | Updated display name |
| `avatar_url` | string | No | URL to avatar image |
| `bio` | string | No | Short biography |
| `skills` | string[] | No | List of skill tags |
| `role_title` | string | No | Job title or role |

**Response `200 OK`:** Returns the updated user profile object.

---

#### `GET /api/auth/users`

List all active users.

- **Auth required:** Yes

**Example Request:**

```bash
curl -H "Authorization: Bearer <token>" https://api.example.com/api/auth/users
```

**Response `200 OK`:**

```json
[
  {
    "id": "uuid-string",
    "username": "jdoe",
    "display_name": "Jane Doe",
    "avatar_url": "https://example.com/avatar.jpg",
    "role_title": "Senior Developer"
  }
]
```

---

### Query (`/api`)

#### `POST /api/query`

Ask a natural-language question against the collective knowledge base.

- **Auth required:** Yes
- **Rate limit:** 10 requests per minute

**Request Body:**

```json
{
  "question": "Who has experience with Kubernetes?",
  "conversation_id": "uuid-string",
  "filters": {},
  "room_id": "uuid-string"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `question` | string | Yes | The question to ask |
| `conversation_id` | string | No | Continue an existing conversation |
| `filters` | object | No | Filter criteria for the search |
| `room_id` | string | No | Scope query to a specific room |

**Response `200 OK`:**

```json
{
  "answer": "Based on the knowledge base, Alice and Bob have significant Kubernetes experience...",
  "sources": [
    {
      "type": "document",
      "title": "Infrastructure Guide",
      "snippet": "...Kubernetes deployment patterns..."
    }
  ],
  "related_members": [
    {
      "id": "uuid-string",
      "name": "Alice Smith",
      "relevance_score": 0.95
    }
  ],
  "conversation_id": "uuid-string"
}
```

**Errors:** `429 Too Many Requests` if rate limit is exceeded.

---

### Members (`/api/members`)

#### `GET /api/members`

List all members with optional filtering.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `room_id` | string | — | Filter by room |
| `limit` | integer | 50 | Max results to return |
| `offset` | integer | 0 | Pagination offset |

**Example Request:**

```bash
curl -H "Authorization: Bearer <token>" \
  "https://api.example.com/api/members?room_id=abc&limit=20&offset=0"
```

**Response `200 OK`:**

```json
[
  {
    "id": "uuid-string",
    "name": "Alice Smith",
    "email": "alice@example.com",
    "expertise_tags": ["python", "machine-learning"],
    "contribution_count": 42
  }
]
```

---

#### `GET /api/members/{id}`

Get detailed member profile including contributions.

- **Auth required:** Yes

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Member UUID |

**Response `200 OK`:**

```json
{
  "id": "uuid-string",
  "name": "Alice Smith",
  "email": "alice@example.com",
  "expertise_tags": ["python", "machine-learning"],
  "contributions": [
    {
      "id": "uuid-string",
      "type": "commit",
      "title": "Add ML pipeline",
      "created_at": "2025-06-01T14:00:00Z"
    }
  ]
}
```

---

#### `POST /api/members`

Create a new member.

- **Auth required:** Yes

**Request Body:**

```json
{
  "name": "Bob Johnson",
  "email": "bob@example.com",
  "expertise_tags": ["react", "typescript"]
}
```

| Field | Type | Required |
|-------|------|----------|
| `name` | string | Yes |
| `email` | string | No |
| `expertise_tags` | string[] | No |

**Response `201 Created`:** Returns the created member object.

---

#### `PUT /api/members/{id}`

Update an existing member.

- **Auth required:** Yes

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Member UUID |

**Request Body:** Same fields as `POST /api/members` (all optional).

**Response `200 OK`:** Returns the updated member object.

---

#### `PUT /api/members/{id}/aliases`

Update the alias list for a member.

- **Auth required:** Yes

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Member UUID |

**Request Body:**

```json
{
  "aliases": ["bob", "bobby", "bob.johnson"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `aliases` | string[] | Yes | List of alternative names/handles |

**Response `200 OK`:** Returns the updated member object.

---

#### `GET /api/members/{id}/contributions`

List contributions for a specific member.

- **Auth required:** Yes

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Member UUID |

**Response `200 OK`:**

```json
[
  {
    "id": "uuid-string",
    "type": "commit",
    "title": "Fix authentication bug",
    "created_at": "2025-06-15T09:00:00Z"
  }
]
```

---

#### `DELETE /api/members/{id}`

Delete a member.

- **Auth required:** Yes

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Member UUID |

**Response `200 OK`:**

```json
{
  "message": "Member deleted successfully."
}
```

---

### Ingest (`/api/ingest`)

#### `POST /api/ingest/git`

Ingest contributions from a Git repository.

- **Auth required:** Yes

**Request Body:**

```json
{
  "repo_path": "/path/to/repo",
  "branch": "main",
  "since_days": 30,
  "room_id": "uuid-string"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `repo_path` | string | Yes | Path to the Git repository |
| `branch` | string | No | Branch to ingest (default: current) |
| `since_days` | integer | No | Only ingest commits from the last N days |
| `room_id` | string | No | Associate data with a room |

**Response `200 OK`:**

```json
{
  "task_id": "uuid-string",
  "status": "processing",
  "message": "Git ingestion started."
}
```

---

#### `POST /api/ingest/markdown`

Ingest Markdown files from a directory.

- **Auth required:** Yes

**Request Body:**

```json
{
  "directory_path": "/path/to/docs",
  "room_id": "uuid-string"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `directory_path` | string | Yes | Path to directory containing Markdown files |
| `room_id` | string | No | Associate data with a room |

**Response `200 OK`:** Returns a task status object.

---

#### `POST /api/ingest/markdown-upload`

Upload Markdown files for ingestion.

- **Auth required:** Yes
- **Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `files` | file(s) | Yes | Markdown files to upload |
| `room_id` | string | No | Associate data with a room |

**Example Request:**

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -F "files=@doc1.md" \
  -F "files=@doc2.md" \
  -F "room_id=uuid-string" \
  https://api.example.com/api/ingest/markdown-upload
```

**Response `200 OK`:** Returns a task status object.

---

#### `POST /api/ingest/documents`

Upload documents for ingestion (PDF, DOCX, TXT, etc.).

- **Auth required:** Yes
- **Content-Type:** `multipart/form-data`
- **Max file size:** 50 MB

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `files` | file(s) | Yes | Document files to upload |
| `room_id` | string | No | Associate data with a room |

**Response `200 OK`:** Returns a task status object.

**Errors:** `413 Payload Too Large` if file exceeds 50 MB.

---

#### `POST /api/ingest/slack`

Ingest Slack export data from a ZIP archive.

- **Auth required:** Yes
- **Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | Slack export ZIP file |
| `room_id` | string | No | Associate data with a room |

**Response `200 OK`:** Returns a task status object.

---

#### `POST /api/ingest/discord`

Ingest Discord export data from a JSON file.

- **Auth required:** Yes
- **Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | Discord export JSON file |
| `room_id` | string | No | Associate data with a room |

**Response `200 OK`:** Returns a task status object.

---

#### `POST /api/ingest/tasks`

Ingest task/project data from a JSON file.

- **Auth required:** Yes
- **Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | Tasks JSON file |
| `room_id` | string | No | Associate data with a room |

**Response `200 OK`:** Returns a task status object.

---

#### `GET /api/ingest/tasks/{task_id}`

Check the status of an ingestion task.

- **Auth required:** Yes

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `task_id` | string | Ingestion task UUID |

**Response `200 OK`:**

```json
{
  "task_id": "uuid-string",
  "status": "completed",
  "progress": 100,
  "message": "Successfully ingested 150 documents.",
  "created_at": "2025-06-01T10:00:00Z",
  "completed_at": "2025-06-01T10:05:00Z"
}
```

Possible `status` values: `pending`, `processing`, `completed`, `failed`.

---

### Rooms (`/api/rooms`)

#### `POST /api/rooms`

Create a new room.

- **Auth required:** Yes

**Request Body:**

```json
{
  "name": "Backend Team",
  "description": "Room for backend engineering discussions",
  "is_public": true
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | — | Room name |
| `description` | string | No | — | Room description |
| `is_public` | boolean | No | `false` | Whether room is publicly discoverable |

**Response `201 Created`:**

```json
{
  "id": "uuid-string",
  "name": "Backend Team",
  "description": "Room for backend engineering discussions",
  "is_public": true,
  "created_by": "uuid-string",
  "created_at": "2025-06-01T10:00:00Z"
}
```

---

#### `GET /api/rooms`

List rooms the authenticated user belongs to.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Max results |
| `offset` | integer | 0 | Pagination offset |

**Response `200 OK`:**

```json
[
  {
    "id": "uuid-string",
    "name": "Backend Team",
    "description": "Room for backend engineering discussions",
    "is_public": true,
    "member_count": 8
  }
]
```

---

#### `GET /api/rooms/discover`

Discover public rooms available to join.

- **Auth required:** Yes

**Response `200 OK`:** Returns an array of public room objects.

---

#### `GET /api/rooms/{room_id}`

Get room details including members and recent messages.

- **Auth required:** Yes

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Room UUID |

**Response `200 OK`:**

```json
{
  "id": "uuid-string",
  "name": "Backend Team",
  "description": "Room for backend engineering discussions",
  "is_public": true,
  "created_by": "uuid-string",
  "members": [
    {
      "user_id": "uuid-string",
      "username": "jdoe",
      "role": "admin"
    }
  ],
  "recent_messages": [
    {
      "id": "uuid-string",
      "user_id": "uuid-string",
      "content": "Hello team!",
      "created_at": "2025-06-01T12:00:00Z"
    }
  ]
}
```

---

#### `PUT /api/rooms/{room_id}`

Update room details. Only room admins can perform this action.

- **Auth required:** Yes (admin only)

**Request Body:**

```json
{
  "name": "Backend Engineering",
  "description": "Updated description",
  "is_public": false
}
```

**Response `200 OK`:** Returns the updated room object.

**Errors:** `403 Forbidden` if the user is not a room admin.

---

#### `POST /api/rooms/{room_id}/join`

Join a public room.

- **Auth required:** Yes

**Response `200 OK`:**

```json
{
  "message": "Successfully joined room."
}
```

**Errors:** `403 Forbidden` if the room is private.

---

#### `POST /api/rooms/{room_id}/members`

Add members to a room.

- **Auth required:** Yes

**Request Body:**

```json
{
  "user_ids": ["uuid-1", "uuid-2"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_ids` | string[] | Yes | List of user UUIDs to add |

**Response `200 OK`:**

```json
{
  "message": "Members added successfully.",
  "added_count": 2
}
```

---

#### `DELETE /api/rooms/{room_id}/members/{user_id}`

Remove a member from a room.

- **Auth required:** Yes

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Room UUID |
| `user_id` | string | User UUID to remove |

**Response `200 OK`:**

```json
{
  "message": "Member removed successfully."
}
```

---

#### `POST /api/rooms/{room_id}/messages`

Send a message to a room.

- **Auth required:** Yes

**Request Body:**

```json
{
  "content": "Hello team!"
}
```

| Field | Type | Required |
|-------|------|----------|
| `content` | string | Yes |

**Response `201 Created`:**

```json
{
  "id": "uuid-string",
  "user_id": "uuid-string",
  "content": "Hello team!",
  "created_at": "2025-06-01T12:00:00Z"
}
```

---

#### `GET /api/rooms/{room_id}/messages`

Retrieve messages from a room with cursor-based pagination.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Max messages to return |
| `before` | string | — | Cursor: return messages before this message ID |

**Response `200 OK`:**

```json
[
  {
    "id": "uuid-string",
    "user_id": "uuid-string",
    "username": "jdoe",
    "content": "Hello team!",
    "created_at": "2025-06-01T12:00:00Z"
  }
]
```

---

#### `POST /api/rooms/{room_id}/ai`

Ask an AI question scoped to the room's knowledge.

- **Auth required:** Yes

**Request Body:**

```json
{
  "question": "What are our deployment best practices?"
}
```

| Field | Type | Required |
|-------|------|----------|
| `question` | string | Yes |

**Response `200 OK`:**

```json
{
  "answer": "Based on the room's knowledge base...",
  "sources": []
}
```

---

#### `WS /api/rooms/ws/{room_id}`

WebSocket connection for real-time room messaging.

- **Auth:** Send `{"token": "<jwt>"}` as the first message after connecting.

See [WebSocket Protocol](#websocket-protocol) for details on message types and usage.

---

### Conversations (`/api/conversations`)

#### `GET /api/conversations`

List the authenticated user's conversations.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Max results |
| `offset` | integer | 0 | Pagination offset |
| `room_id` | string | — | Filter by room |

**Response `200 OK`:**

```json
[
  {
    "id": "uuid-string",
    "title": "Kubernetes expertise",
    "created_at": "2025-06-01T10:00:00Z",
    "message_count": 5
  }
]
```

---

#### `GET /api/conversations/{id}`

Get a conversation with its full message history.

- **Auth required:** Yes

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Conversation UUID |

**Response `200 OK`:**

```json
{
  "id": "uuid-string",
  "title": "Kubernetes expertise",
  "messages": [
    {
      "role": "user",
      "content": "Who knows Kubernetes?",
      "created_at": "2025-06-01T10:00:00Z"
    },
    {
      "role": "assistant",
      "content": "Alice and Bob have experience...",
      "created_at": "2025-06-01T10:00:01Z"
    }
  ],
  "created_at": "2025-06-01T10:00:00Z"
}
```

---

#### `DELETE /api/conversations/{id}`

Delete a conversation. Only the owner can delete it.

- **Auth required:** Yes (owner only)

**Response `200 OK`:**

```json
{
  "message": "Conversation deleted successfully."
}
```

**Errors:** `403 Forbidden` if the user is not the conversation owner.

---

#### `POST /api/conversations/{id}/share`

Share a conversation with other users.

- **Auth required:** Yes

**Request Body:**

```json
{
  "user_ids": ["uuid-1", "uuid-2"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_ids` | string[] | Yes | Users to share with |

**Response `200 OK`:**

```json
{
  "message": "Conversation shared successfully."
}
```

---

#### `GET /api/conversations/{id}/participants`

List participants in a shared conversation.

- **Auth required:** Yes

**Response `200 OK`:**

```json
[
  {
    "user_id": "uuid-string",
    "username": "jdoe",
    "added_at": "2025-06-01T10:00:00Z"
  }
]
```

---

#### `DELETE /api/conversations/{id}/participants/{user_id}`

Remove a participant from a shared conversation.

- **Auth required:** Yes

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Conversation UUID |
| `user_id` | string | Participant UUID to remove |

**Response `200 OK`:**

```json
{
  "message": "Participant removed successfully."
}
```

---

### Discussions (`/api/discussions`)

#### `POST /api/discussions`

Create a new discussion thread.

- **Auth required:** Yes

**Request Body:**

```json
{
  "title": "API Design Review",
  "context_type": "document",
  "context_id": "uuid-string",
  "room_id": "uuid-string"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Yes | Thread title |
| `context_type` | string | No | Type of context (e.g., `document`, `query`) |
| `context_id` | string | No | ID of the related context entity |
| `room_id` | string | No | Associate with a room |

**Response `201 Created`:**

```json
{
  "id": "uuid-string",
  "title": "API Design Review",
  "created_by": "uuid-string",
  "created_at": "2025-06-01T10:00:00Z"
}
```

---

#### `GET /api/discussions`

List discussion threads with optional filters.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `context_type` | string | Filter by context type |
| `context_id` | string | Filter by context ID |
| `room_id` | string | Filter by room |

**Response `200 OK`:**

```json
[
  {
    "id": "uuid-string",
    "title": "API Design Review",
    "message_count": 12,
    "created_at": "2025-06-01T10:00:00Z"
  }
]
```

---

#### `GET /api/discussions/{thread_id}`

Get a discussion thread with its messages.

- **Auth required:** Yes

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `thread_id` | string | Thread UUID |

**Response `200 OK`:**

```json
{
  "id": "uuid-string",
  "title": "API Design Review",
  "messages": [
    {
      "id": "uuid-string",
      "user_id": "uuid-string",
      "content": "I think we should use REST.",
      "created_at": "2025-06-01T10:05:00Z"
    }
  ],
  "created_at": "2025-06-01T10:00:00Z"
}
```

---

#### `WS /api/discussions/ws/{thread_id}`

WebSocket connection for real-time discussion thread messaging.

- **Auth:** Send `{"token": "<jwt>"}` as the first message after connecting.

See [WebSocket Protocol](#websocket-protocol) for details.

---

### Insights (`/api/insights`)

#### `GET /api/insights/dashboard`

Get dashboard summary data.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Scope to a specific room |

**Response `200 OK`:**

```json
{
  "total_members": 25,
  "total_contributions": 1250,
  "total_topics": 85,
  "active_members_7d": 18,
  "recent_activity": []
}
```

---

#### `GET /api/insights/weekly`

Get a weekly summary of activity and insights.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Scope to a specific room |

**Response `200 OK`:**

```json
{
  "period_start": "2025-05-26",
  "period_end": "2025-06-01",
  "highlights": [],
  "top_contributors": [],
  "trending_topics": []
}
```

---

#### `GET /api/insights/patterns`

Get detected knowledge patterns and trends.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Scope to a specific room |

**Response `200 OK`:**

```json
{
  "patterns": [
    {
      "type": "expertise_cluster",
      "description": "Strong overlap between ML and data engineering skills",
      "members": ["uuid-1", "uuid-2"],
      "confidence": 0.87
    }
  ]
}
```

---

#### `POST /api/insights/generate`

Trigger generation of new insights from current data.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Scope to a specific room |

**Response `200 OK`:**

```json
{
  "message": "Insight generation started.",
  "task_id": "uuid-string"
}
```

---

#### `GET /api/insights/freshness`

Get a data freshness report showing when each data source was last updated.

- **Auth required:** Yes

**Response `200 OK`:**

```json
{
  "sources": [
    {
      "type": "git",
      "last_ingested": "2025-06-01T10:00:00Z",
      "record_count": 500,
      "freshness": "fresh"
    }
  ]
}
```

---

#### `GET /api/insights/freshness/alerts`

Get the top 10 stale data alerts.

- **Auth required:** Yes

**Response `200 OK`:**

```json
{
  "alerts": [
    {
      "source": "slack",
      "last_ingested": "2025-04-01T10:00:00Z",
      "days_stale": 61,
      "severity": "high"
    }
  ]
}
```

---

### Graph (`/api/graph`)

#### `GET /api/graph/full`

Get the full knowledge graph.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Scope to a specific room |

**Response `200 OK`:**

```json
{
  "nodes": [
    {
      "id": "uuid-string",
      "type": "member",
      "label": "Alice Smith",
      "properties": {}
    }
  ],
  "edges": [
    {
      "source": "uuid-1",
      "target": "uuid-2",
      "type": "collaborates_with",
      "weight": 0.85
    }
  ]
}
```

---

#### `GET /api/graph/member/{member_id}`

Get the knowledge subgraph centered on a specific member.

- **Auth required:** Yes

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `member_id` | string | Member UUID |

**Response `200 OK`:** Returns a graph object with `nodes` and `edges` related to the member.

---

#### `GET /api/graph/topic/{topic}`

Get the knowledge subgraph for a specific topic.

- **Auth required:** Yes

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `topic` | string | Topic name or keyword |

**Response `200 OK`:** Returns a graph object with `nodes` and `edges` related to the topic.

---

#### `GET /api/graph/expertise-matrix`

Get the expertise matrix showing member-to-skill relationships.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Scope to a specific room |

**Response `200 OK`:**

```json
{
  "members": ["Alice", "Bob"],
  "skills": ["python", "react", "kubernetes"],
  "matrix": [
    [0.9, 0.3, 0.7],
    [0.5, 0.8, 0.2]
  ]
}
```

---

#### `GET /api/graph/stats`

Get graph statistics.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Scope to a specific room |

**Response `200 OK`:**

```json
{
  "total_nodes": 150,
  "total_edges": 420,
  "node_types": {
    "member": 25,
    "topic": 85,
    "document": 40
  },
  "density": 0.037,
  "avg_degree": 5.6
}
```

---

#### `GET /api/graph/clusters`

Get community clusters detected in the knowledge graph.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Scope to a specific room |

**Response `200 OK`:**

```json
{
  "clusters": [
    {
      "id": 0,
      "label": "Frontend Team",
      "members": ["uuid-1", "uuid-2"],
      "topics": ["react", "css", "typescript"],
      "size": 5
    }
  ]
}
```

---

#### `GET /api/graph/expertise-gaps`

Identify expertise gaps in the team.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Scope to a specific room |

**Response `200 OK`:**

```json
{
  "gaps": [
    {
      "skill": "security",
      "demand_score": 0.8,
      "coverage_score": 0.2,
      "gap_severity": "high"
    }
  ]
}
```

---

### Analytics (`/api/analytics`)

#### `GET /api/analytics/activity-timeline`

Get an activity timeline over a period of days.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 30 | Number of days to look back |
| `room_id` | string | — | Scope to a specific room |

**Response `200 OK`:**

```json
{
  "timeline": [
    {
      "date": "2025-06-01",
      "contributions": 15,
      "queries": 8,
      "active_members": 6
    }
  ]
}
```

---

#### `GET /api/analytics/source-breakdown`

Get a breakdown of contributions by source type.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Scope to a specific room |

**Response `200 OK`:**

```json
{
  "sources": [
    {"type": "git", "count": 500, "percentage": 40.0},
    {"type": "slack", "count": 375, "percentage": 30.0},
    {"type": "document", "count": 375, "percentage": 30.0}
  ]
}
```

---

#### `GET /api/analytics/expertise-matrix`

Get an expertise matrix visualization.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Scope to a specific room |

**Response `200 OK`:** Returns an expertise matrix similar to `/api/graph/expertise-matrix`.

---

#### `GET /api/analytics/contribution-types`

Get contribution breakdown by type.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Scope to a specific room |

**Response `200 OK`:**

```json
{
  "types": [
    {"type": "commit", "count": 300},
    {"type": "message", "count": 500},
    {"type": "document", "count": 200}
  ]
}
```

---

#### `GET /api/analytics/member-activity`

Get per-member activity metrics.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Scope to a specific room |

**Response `200 OK`:**

```json
[
  {
    "member_id": "uuid-string",
    "name": "Alice Smith",
    "total_contributions": 120,
    "last_active": "2025-06-01T14:00:00Z"
  }
]
```

---

#### `GET /api/analytics/topic-trends`

Get trending topics over time.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Scope to a specific room |

**Response `200 OK`:**

```json
{
  "trends": [
    {
      "topic": "kubernetes",
      "current_count": 25,
      "previous_count": 10,
      "growth_rate": 1.5
    }
  ]
}
```

---

#### `GET /api/analytics/health`

Get a team health snapshot.

- **Auth required:** Yes

**Response `200 OK`:**

```json
{
  "overall_score": 82,
  "dimensions": {
    "collaboration": 85,
    "knowledge_sharing": 78,
    "coverage": 80,
    "activity": 84
  },
  "generated_at": "2025-06-01T10:00:00Z"
}
```

---

#### `GET /api/analytics/health/trends`

Get team health trends over time.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 30 | Number of days to look back |

**Response `200 OK`:**

```json
{
  "trends": [
    {
      "date": "2025-06-01",
      "overall_score": 82,
      "collaboration": 85,
      "knowledge_sharing": 78
    }
  ]
}
```

---

#### `POST /api/analytics/health/snapshot`

Save a health snapshot for historical tracking.

- **Auth required:** Yes

**Response `201 Created`:**

```json
{
  "message": "Health snapshot saved.",
  "snapshot_id": "uuid-string"
}
```

---

### Artifacts (`/api/artifacts`)

#### `GET /api/artifacts`

List all artifacts.

- **Auth required:** Yes

**Response `200 OK`:**

```json
[
  {
    "id": "uuid-string",
    "title": "Architecture Diagram",
    "type": "document",
    "created_at": "2025-06-01T10:00:00Z"
  }
]
```

---

#### `GET /api/artifacts/{id}`

Get artifact details.

- **Auth required:** Yes

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Artifact UUID |

**Response `200 OK`:**

```json
{
  "id": "uuid-string",
  "title": "Architecture Diagram",
  "type": "document",
  "content": "...",
  "metadata": {},
  "created_at": "2025-06-01T10:00:00Z"
}
```

---

#### `DELETE /api/artifacts/{id}`

Delete an artifact.

- **Auth required:** Yes

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Artifact UUID |

**Response `200 OK`:**

```json
{
  "message": "Artifact deleted successfully."
}
```

---

### Search (`/api/search`)

#### `GET /api/search`

Cross-entity search across members, documents, topics, and contributions.

- **Auth required:** Yes

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | — | Search query (required) |
| `limit` | integer | 20 | Max results |
| `room_id` | string | — | Scope to a specific room |
| `semantic` | boolean | `false` | Use semantic (vector) search instead of keyword |

**Example Request:**

```bash
curl -H "Authorization: Bearer <token>" \
  "https://api.example.com/api/search?q=kubernetes&limit=10&semantic=true"
```

**Response `200 OK`:**

```json
{
  "results": [
    {
      "type": "member",
      "id": "uuid-string",
      "title": "Alice Smith",
      "snippet": "Expert in Kubernetes and cloud infrastructure...",
      "score": 0.92
    },
    {
      "type": "document",
      "id": "uuid-string",
      "title": "K8s Deployment Guide",
      "snippet": "...Kubernetes deployment patterns and best practices...",
      "score": 0.88
    }
  ],
  "total": 15
}
```

---

### Slack Integration (`/api/slack`)

Endpoints for Slack bot integration. These are typically called by Slack's event subscription system.

- **Auth:** Verified via Slack signing secret.

---

### GitHub Integration (`/api/github`)

Webhook endpoint for GitHub events (push, pull request, etc.).

- **Auth:** Verified via GitHub webhook secret.

---

### Expert Routing (`/api/experts`)

Endpoints for routing questions to the most relevant team experts.

- **Auth required:** Yes

---

*This documentation covers the Collective Brain REST API. For questions or issues, please refer to the project repository.*
