# Collective Brain - Architecture

## 1. System Overview

Collective Brain is an AI-powered shared memory and strategy platform for small teams. It ingests knowledge from multiple sources (Git repositories, Markdown files, PDF/DOCX documents, Slack channels, Discord, task trackers), builds a searchable vector knowledge base, and provides an intelligent conversational interface powered by LLMs. Teams can collaborate through rooms, discussions, and real-time chat while the system automatically surfaces insights, tracks expertise, and monitors team health.

The platform follows a modern full-stack architecture: a React 19 single-page application communicates with a FastAPI backend that orchestrates data ingestion, retrieval-augmented generation (RAG), agent-based reasoning, and real-time collaboration features.

---

## 2. Architecture Diagram

```
                           +---------------------------+
                           |     React 19 SPA (Vite)   |
                           |  Tailwind CSS | Router 7  |
                           +-------------+-------------+
                                         |
                              HTTPS / WebSocket
                                         |
                           +-------------v-------------+
                           |    Nginx (production)     |
                           |   /api -> backend:8000    |
                           |   /*   -> static SPA      |
                           +-------------+-------------+
                                         |
                +------------------------v------------------------+
                |               FastAPI Application               |
                |                                                 |
                |  +-------------------------------------------+  |
                |  |           Middleware Stack                 |  |
                |  |  CORS -> SecurityHeaders -> RequestID     |  |
                |  +-------------------------------------------+  |
                |                                                 |
                |  +-------------------------------------------+  |
                |  |          Router Layer (16 routers)         |  |
                |  |  /api/health    /api/ingest   /api/query  |  |
                |  |  /api/members   /api/insights /api/graph  |  |
                |  |  /api/conversations /api/artifacts         |  |
                |  |  /api/analytics /api/search   /api/auth   |  |
                |  |  /api/discussions /api/rooms  /api/slack   |  |
                |  |  /api/github    /api/experts              |  |
                |  +-------------------------------------------+  |
                |                                                 |
                |  +-------------------------------------------+  |
                |  |            Service Layer (20+)            |  |
                |  |  RAG Pipeline   | Agent Pipeline (LangGraph)|
                |  |  LLM Service    | Embedding Service       |  |
                |  |  Vector Store   | Memory Graph             |  |
                |  |  Insight Engine | Auth Service             |  |
                |  |  Redis Service  | Task Queue               |  |
                |  |  Circuit Breaker| Digest Service           |  |
                |  |  Team Health    | Freshness Service        |  |
                |  |  Slack Service  | GitHub Event Processor   |  |
                |  +-------------------------------------------+  |
                |                                                 |
                +----+----------+----------+----------+----------+
                     |          |          |          |
              +------v--+ +----v-----+ +--v-------+ +v-----------+
              |PostgreSQL| |  Redis   | | ChromaDB | | LLM Provider|
              | /SQLite  | | (pub/sub | | (vectors)| | Claude/     |
              | (ORM:    | |  cache,  | |          | | Ollama/     |
              | SQLAlch.)|  queues)  | |          | | Mistral/HF  |
              +---------+ +----------+ +----------+ +-------------+
```

---

## 3. Backend Architecture

### 3.1 FastAPI Application Structure

The backend is a FastAPI application (`app/main.py`) that uses the **lifespan** context manager pattern for startup and shutdown lifecycle management.

**Startup sequence:**
1. Load settings from environment variables (via Pydantic `BaseSettings` with `CB_` prefix)
2. Initialize the database (PostgreSQL or SQLite with auto-detection)
3. Connect to Redis (graceful fallback to in-memory if unavailable)
4. Start the background task queue (max 3 concurrent tasks)
5. Initialize core services: embedding service, vector store, LLM service
6. Configure circuit breakers for external service calls
7. Initialize Redis references in WebSocket-enabled routers (rooms, discussions)
8. Auto-generate JWT secret if not provided (persisted to `/data/.cb_jwt_secret`)
9. Eager-load embedding model to avoid first-query latency

**Shutdown sequence:**
1. Flush SQLite WAL checkpoint (if using SQLite)
2. Stop the background task queue
3. Close Redis connection

### 3.2 Middleware Stack

Middleware is applied in reverse order (last added executes first):

| Order | Middleware | Purpose |
|-------|-----------|---------|
| 1 | `RequestIDMiddleware` | Attaches a unique request ID (from `X-Request-ID` header or auto-generated UUID) to every request via `contextvars`. Injects into all log records for distributed tracing. |
| 2 | `SecurityHeadersMiddleware` | Adds security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Referrer-Policy`, `Permissions-Policy`, and HSTS for HTTPS. |
| 3 | `CORSMiddleware` | Configures allowed origins (`localhost:5173`, `localhost:3000`, `CB_CORS_ORIGIN` env var). On HuggingFace Spaces, wildcards all origins for iframe embedding. |

### 3.3 Router Layer

All 16 routers are mounted under the `/api` prefix to avoid collision with SPA routes:

| Router | Prefix | Description |
|--------|--------|-------------|
| `health` | `/api/health` | Health check and system status |
| `ingest` | `/api/ingest` | Data ingestion (Git, Markdown, documents) |
| `query` | `/api` | AI query endpoint (RAG + agent) |
| `members` | `/api/members` | Team member CRUD and aliases |
| `insights` | `/api/insights` | Dashboard, weekly summary, patterns, freshness |
| `graph` | `/api/graph` | Knowledge graph, expertise matrix, clusters |
| `conversations` | `/api/conversations` | Chat conversation history and sharing |
| `artifacts` | `/api/artifacts` | Ingested artifact management |
| `analytics` | `/api/analytics` | Activity timeline, source breakdown, team health |
| `search` | `/api/search` | Full-text and semantic search |
| `auth` | `/api/auth` | Registration, login, JWT, Google OAuth, password reset |
| `discussions` | `/api/discussions` | Threaded discussion forums (WebSocket) |
| `rooms` | `/api/rooms` | Collaborative rooms with real-time chat (WebSocket) |
| `slack` | `/api/slack` | Slack OAuth, channel sync, digest scheduling |
| `github_webhooks` | `/api/github` | GitHub webhook ingestion (PR, issues, commits) |
| `expert_routing` | `/api/experts` | Expert recommendation and help requests |

### 3.4 Service Layer

The service layer contains 20+ services organized by responsibility:

**AI and Knowledge Services:**
- `rag_pipeline.py` - Retrieval-Augmented Generation: embeds questions, searches vectors, assembles context, calls LLM
- `agent_pipeline.py` - LangGraph-based agent with tool calls (search, analyze, recommend) and multi-step reasoning
- `agent_tools.py` - Tool definitions for the LangGraph agent
- `llm_service.py` - Unified LLM interface supporting Claude (Anthropic API), Ollama (local), and Mistral/HuggingFace Inference
- `embedding_service.py` - SentenceTransformers embedding generation (`all-MiniLM-L6-v2`, 384 dimensions)
- `vector_store.py` - ChromaDB vector store for similarity search with metadata filtering
- `memory_graph.py` - NetworkX-based knowledge graph: member-topic relationships, expertise mapping, cluster detection
- `insight_engine.py` - AI-driven pattern detection, weekly summaries, and dashboard generation
- `prompts.py` - Centralized prompt templates for all LLM interactions

**Infrastructure Services:**
- `auth_service.py` - JWT authentication, bcrypt password hashing, Google OAuth verification
- `redis_service.py` - Redis client with pub/sub for WebSocket fan-out; graceful in-memory fallback
- `task_queue.py` - Async background task queue with concurrency limiting (max 3 workers)
- `circuit_breaker.py` - Circuit breaker pattern for external services (embedding, LLM) with configurable failure thresholds and recovery timeouts

**Integration Services:**
- `slack_service.py` - Slack API client for OAuth, channel listing, message fetching
- `slack_event_processor.py` - Processes incoming Slack events into knowledge chunks
- `github_event_processor.py` - Processes GitHub webhook payloads (PRs, issues, commits)
- `digest_service.py` - Generates and sends weekly knowledge digests to Slack channels
- `freshness_service.py` - Tracks knowledge staleness and generates freshness alerts
- `team_health_service.py` - Computes team health metrics, trends, and predictions

### 3.5 Data Layer

**ORM and Database:**
- SQLAlchemy 2.0 ORM with 9 models:
  - `User` - Authentication accounts (username, email, bcrypt password hash)
  - `Member` - Team members with aliases and expertise topics
  - `Contribution` - Knowledge contributions linked to members and artifacts
  - `Conversation` - AI chat conversations with sharing/participant support
  - `Artifact` - Ingested source artifacts (Git repos, files, Slack channels)
  - `Discussion` - Threaded discussion forums
  - `Insight` - AI-generated insights and patterns
  - `Room` - Collaborative team rooms
  - `SlackIntegration` - Slack workspace OAuth tokens and sync configuration

**Database Support:**
- **SQLite** (default for local development) - Auto-created at `./data/collective_brain.db`. WAL mode enabled. Checkpoint flushed on graceful shutdown.
- **PostgreSQL** (recommended for production) - Connection pooling via SQLAlchemy: pool size 10, max overflow 20, 30-minute recycle.

**Migrations:**
- Alembic with auto-detection of model changes. Migration scripts stored in `backend/alembic/versions/`.

### 3.6 Vector Store

- **ChromaDB** with persistent storage at `CB_CHROMA_PERSIST_DIR` (default: `./data/chroma_db`)
- **Embeddings:** SentenceTransformers `all-MiniLM-L6-v2` model (384 dimensions)
- **Chunking:** Configurable chunk size (default 512 tokens) with overlap (default 64 tokens)
- **Retrieval:** Top-K similarity search (default K=8) with context assembly up to 3000 tokens

### 3.7 Ingestion System

The ingestion system uses a connector-based architecture with a central registry:

| Connector | Source | Description |
|-----------|--------|-------------|
| `GitConnector` | Git repositories | Extracts commits, diffs, and file contents |
| `MarkdownConnector` | Markdown files/directories | Parses `.md` files with metadata extraction |
| `DocumentConnector` | PDF/DOCX files | Extracts text via PyMuPDF and python-docx |
| `SlackConnector` | Slack channels | Ingests messages via Slack API |
| `DiscordConnector` | Discord channels | Ingests messages via Discord API |
| `TaskConnector` | Task trackers | Ingests task/issue data |

All connectors extend `BaseConnector` and are registered in `registry.py`. The `get_connector()` factory creates instances by source type.

### 3.8 Real-time Communication

- WebSocket connections in the `rooms` and `discussions` routers
- Redis pub/sub for multi-process message fan-out (when Redis is available)
- Graceful fallback to in-process message broadcasting when Redis is unavailable
- WebSocket limits enforced for connection security

---

## 4. Frontend Architecture

### 4.1 Technology Stack

- **React 19** with TypeScript 5.9
- **Vite 7** for development server and production builds
- **Tailwind CSS 4** with dark/light theme support via `@tailwindcss/vite`
- **React Router 7** for client-side routing with protected routes

### 4.2 Routing and Code Splitting

Routes are defined in `App.tsx` with two tiers:

**Public routes** (no authentication required):
- `/login`, `/register`, `/forgot-password`

**Protected routes** (wrapped in `ProtectedRoute` + `PageShell` layout):
- `/` - Dashboard
- `/chat` - AI Chat
- `/ingest` - Data Ingestion
- `/members`, `/members/:id` - Team Members
- `/graph` - Knowledge Graph (lazy-loaded)
- `/analytics` - Analytics (lazy-loaded)
- `/health` - Team Health (lazy-loaded)
- `/rooms`, `/rooms/:roomId` - Collaborative Rooms (lazy-loaded)
- `/discussions` - Threaded Discussions (lazy-loaded)
- `/settings` - User Settings

Heavy pages are lazy-loaded with `React.lazy()` to reduce initial bundle size: `GraphPage`, `AnalyticsPage`, `DiscussionsPage`, `RoomChatPage`, `TeamHealthPage`.

Every route is wrapped in `FeatureErrorBoundary` for isolated error handling and a `Suspense` fallback with a loading spinner.

### 4.3 State Management

State is managed through custom React hooks:

| Hook | Purpose |
|------|---------|
| `useAuth` | JWT token management, login/logout, user profile, authentication state |
| `useChat` | AI chat state, message history, streaming responses |
| `useRoom` | Room membership, real-time WebSocket messages, room-scoped data |
| `useDiscussion` | Discussion threads, threaded messages, WebSocket updates |
| `useTheme` | Dark/light theme toggle with system preference detection |
| `useGoogleAuth` | Google OAuth flow integration via `@react-oauth/google` |

### 4.4 API Client

All API communication flows through a centralized client (`src/api/client.ts`):

- Base URL configured via `VITE_API_BASE` environment variable (defaults to `/api`)
- Automatic JWT token injection from `localStorage` into `Authorization: Bearer` headers
- Global 401 handling: clears token and redirects to `/login`
- Typed request/response interfaces for all endpoints
- `AbortSignal` support for request cancellation

### 4.5 Key Libraries

| Library | Purpose |
|---------|---------|
| `react-force-graph-2d` | Interactive knowledge graph visualization |
| `recharts` | Analytics charts and data visualization |
| `react-markdown` + `remark-gfm` | Markdown rendering in chat and discussions |
| `framer-motion` | Page transitions and UI animations |
| `lucide-react` | Icon library |
| `@react-oauth/google` | Google OAuth sign-in button |

### 4.6 Styling

- Tailwind CSS 4 integrated via the Vite plugin (`@tailwindcss/vite`)
- Dark/light theme support managed by `useTheme` hook
- Responsive design for desktop and mobile viewports

---

## 5. Data Flow

### 5.1 Ingestion Pipeline

```
Source (Git/Markdown/PDF/Slack/Discord)
    |
    v
Connector (extends BaseConnector)
    |  - Extracts raw content
    |  - Attaches metadata (author, date, source_type)
    v
Chunker
    |  - Splits content into chunks (512 tokens, 64 overlap)
    |  - Preserves metadata per chunk
    v
Embedding Service (SentenceTransformers)
    |  - Generates 384-dim vectors for each chunk
    v
+---+---+
|       |
v       v
ChromaDB   SQLAlchemy (Artifact + Contribution records)
(vectors)  (relational metadata, member attribution)
```

### 5.2 Query Pipeline (RAG Mode)

```
User Question
    |
    v
Embedding Service
    |  - Embed the question into 384-dim vector
    v
Vector Store (ChromaDB)
    |  - Top-K similarity search (K=8)
    |  - Metadata filtering (room, source_type, date range)
    v
Context Assembly
    |  - Rank and deduplicate chunks
    |  - Trim to context_max_tokens (3000)
    v
LLM Service (Claude / Ollama / Mistral)
    |  - System prompt + assembled context + user question
    |  - Generate grounded response with citations
    v
Response (answer + sources + conversation tracking)
```

### 5.3 Agent Pipeline (LangGraph Mode)

```
User Question
    |
    v
LangGraph State Machine
    |
    +---> Tool: search (vector similarity search)
    |
    +---> Tool: analyze (cross-reference knowledge)
    |
    +---> Tool: recommend (expert routing, suggestions)
    |
    v
Multi-step Reasoning (max 10 iterations)
    |
    v
Final Response (synthesized answer + tool call traces)
```

---

## 6. Security Architecture

### 6.1 Authentication and Authorization

- **JWT tokens** with HS256 signing, 30-minute expiry (configurable via `CB_JWT_EXPIRE_MINUTES`)
- **Password hashing** with bcrypt via `passlib`
- **Google OAuth** verification using `google-auth` library
- **Auto-generated JWT secret** persisted to disk for container restart resilience

### 6.2 Rate Limiting

- General API: 60 requests per minute per user
- AI query endpoints: 10 requests per minute per user (configurable via `CB_RATE_LIMIT_AI_REQUESTS`)

### 6.3 Transport Security

- **CORS** with explicit origin allowlist (no wildcards in production)
- **Security headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Referrer-Policy`, `Permissions-Policy`, HSTS
- **Content Security Policy** enforced via headers

### 6.4 Resilience Patterns

- **Circuit breaker** for external services (embedding, LLM): opens after 5 consecutive failures, recovers after 60 seconds. Returns HTTP 503 with `Retry-After` header when open.
- **ZIP bomb protection** on file upload endpoints
- **WebSocket connection limits** to prevent resource exhaustion
- **Path traversal prevention** in SPA static file serving (resolves and validates paths against the static directory)

### 6.5 Global Error Handling

- `CircuitBreakerError` mapped to HTTP 503 with retry information
- Global exception handler catches unhandled errors, logs with request ID, returns generic 500

---

## 7. Deployment Architecture

### 7.1 Docker (Multi-Stage Build)

The root `Dockerfile` uses a two-stage build:

1. **Stage 1 (frontend-build):** `node:20-slim` - installs dependencies, builds the React app with `VITE_API_BASE="/api"`
2. **Stage 2 (backend):** `python:3.11-slim` - installs CPU-only PyTorch, Python dependencies, copies backend code, copies built frontend into `./static` for FastAPI to serve

Single-worker deployment by default (WebSocket connections are process-local).

### 7.2 Docker Compose

The `docker-compose.yml` defines 5 services:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `postgres` | `postgres:16-alpine` | 5432 | Primary database with health checks |
| `redis` | `redis:7-alpine` | 6379 | Pub/sub, caching, task queue backend (256MB max, LRU eviction) |
| `backend` | Custom (Dockerfile) | 8000 | FastAPI application server |
| `frontend` | Custom (Dockerfile) | 3000 (Nginx:80) | React SPA served via Nginx |
| `worker` | Custom (backend Dockerfile) | - | Celery worker for background tasks (concurrency=2) |

Named volumes: `pgdata`, `redisdata`, `backend_data`.

### 7.3 Render.com

Defined in `render.yaml`:
- Single web service using the root Docker image
- Free tier plan
- Persistent disk (`cb-data`, 1GB) mounted at `/app/data`
- Default LLM provider: Mistral (via HuggingFace Inference API)
- Auto-generated JWT secret

### 7.4 HuggingFace Spaces

- Uses the same Docker image with port 7860
- Persistent storage at `/data` (must be enabled in Space settings)
- SQLite database at `/data/collective_brain.db`
- ChromaDB at `/data/chroma_db`
- LLM via HuggingFace Inference API (uses `HF_TOKEN` auto-set by HF runtime)
- CORS set to wildcard (`*`) for iframe embedding
- JWT secret persisted to `/data/.cb_jwt_secret`
- Boot marker at `/data/.cb_persistence_marker` to verify storage persistence
