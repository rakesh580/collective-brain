<div align="center">

# :brain: Collective Brain

**AI-Powered Team Knowledge Management Platform**

[![CI](https://github.com/your-org/collective-brain/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/collective-brain/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React 19](https://img.shields.io/badge/react-19-61dafb.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178c6.svg)](https://www.typescriptlang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ed.svg)](https://www.docker.com/)

Ingest your team's work — git repos, documents, Slack exports, Discord logs — and transform it into a searchable, AI-powered knowledge base with real-time collaboration, knowledge graphs, and expert routing.

[Quick Start](#-quick-start) · [Features](#-features) · [Architecture](#-architecture) · [API Reference](#-api-reference) · [Deployment](#-deployment)

</div>

---

## :mag: Overview

Collective Brain is a full-stack platform that turns scattered team knowledge into an intelligent, queryable system. It combines **Retrieval-Augmented Generation (RAG)** with real-time collaboration tools so teams can discover expertise, share context, and get AI-powered answers grounded in their own data.

**Key capabilities:**
- Ingest **7 source types** (git, markdown, PDF, DOCX, TXT, Slack, Discord)
- Query your knowledge base with a **RAG pipeline** or an **agentic LangGraph** pipeline
- Visualize relationships with an interactive **knowledge graph**
- Collaborate in **real-time chat rooms** with an embedded AI assistant
- Automatically discover **team experts** and route questions to them

---

## :sparkles: Features

### :inbox_tray: Data Ingestion
Ingest from multiple sources — git repositories, markdown directories, PDF/DOCX/TXT uploads, Slack exports, Discord exports, and task JSON files. Each source is chunked, embedded, and stored in ChromaDB for semantic retrieval.

### :robot: AI Q&A
Ask natural-language questions and get answers grounded in your team's data. Supports two modes:
- **RAG mode** — fast retrieval + generation with source attribution
- **LangGraph agent mode** — multi-step reasoning with tool use across your knowledge base

### :speech_balloon: Real-Time Rooms
WebSocket-powered chat rooms with typing indicators, user presence tracking, message history, and an in-room AI assistant that answers questions scoped to the room's context.

### :globe_with_meridians: Knowledge Graph
Interactive force-directed graph visualization showing relationships between team members, artifacts, and topics. Includes mind maps, heatmaps, expertise matrices, and community detection.

### :busts_in_silhouette: Team Members
Auto-discovered from ingested data with expertise scoring, contribution tracking, and skill tagging. Members can also be created and managed manually.

### :bar_chart: Analytics
Activity timelines, source breakdowns, topic trends, and team health metrics — all derived from your ingested data and team interactions.

### :left_speech_bubble: Discussions
Async threaded discussions with real-time WebSocket updates. Attach discussions to members, insights, or use them as standalone topic threads.

### :bulb: Insights
AI-generated weekly summaries, pattern detection, and data freshness monitoring to keep your team informed about knowledge base health and emerging trends.

### :electric_plug: Integrations
- **Slack** — OAuth integration with automated digest delivery
- **GitHub** — Webhook support with signature verification for automatic ingestion

### :dart: Expert Routing
Automatic expert recommendation based on expertise scoring — route questions to the right person on your team.

---

## :camera: Screenshots

> **Coming soon** — Screenshots and demo GIFs will be added here.

<!--
| Dashboard | Knowledge Graph | Chat Room |
|:-:|:-:|:-:|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Graph](docs/screenshots/graph.png) | ![Room](docs/screenshots/room.png) |
-->

---

## :rocket: Quick Start

### Docker (Recommended)

The fastest way to get the full stack running with PostgreSQL, Redis, and all services.

```bash
# Clone the repository
git clone https://github.com/your-org/collective-brain.git
cd collective-brain

# Configure environment
cp .env.example .env
# Edit .env — set CB_POSTGRES_PASSWORD, CB_REDIS_PASSWORD, CB_JWT_SECRET
# Generate secrets: openssl rand -base64 32

# Start all services
docker-compose up -d

# The app will be available at:
#   Frontend:   http://localhost:3000
#   Backend:    http://localhost:8000
#   PostgreSQL: localhost:5432
#   Redis:      localhost:6379
```

### Local Development

#### Prerequisites
- Python 3.11+
- Node.js 20+
- (Optional) [Ollama](https://ollama.com) for local LLM inference
- (Optional) PostgreSQL 16+ and Redis 7+ (SQLite used by default in dev)

#### Backend

```bash
cd backend

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server (proxies API to backend on port 8000)
npm run dev
```

The frontend will be available at **http://localhost:5173**.

#### First Steps

1. Open http://localhost:5173 — you will be redirected to the registration page
2. Create an account
3. Navigate to **Ingest** and import a git repository or upload documents
4. Go to **Chat** and ask AI questions about your team's knowledge
5. Create a **Room** to collaborate in real-time with teammates
6. Explore the **Graph** to visualize relationships across your knowledge base

---

## :gear: Configuration

All backend settings use the `CB_` prefix and are loaded via [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).

### Required (Production)

| Variable | Description |
|----------|-------------|
| `CB_JWT_SECRET` | JWT signing secret — generate with `openssl rand -base64 64` |
| `CB_POSTGRES_PASSWORD` | PostgreSQL password (Docker setup) |
| `CB_REDIS_PASSWORD` | Redis password (Docker setup) |

### LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CB_LLM_PROVIDER` | `ollama` | Provider: `ollama`, `claude`, or `mistral` |
| `CB_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `CB_OLLAMA_MODEL` | `llama3.1:8b` | Ollama model name |
| `CB_CLAUDE_API_KEY` | — | Anthropic API key (required if provider=claude) |
| `CB_CLAUDE_MODEL` | `claude-sonnet-4-20250514` | Claude model ID |
| `CB_MISTRAL_API_KEY` | — | HuggingFace token (required if provider=mistral) |
| `CB_MISTRAL_MODEL` | `Qwen/Qwen2.5-72B-Instruct` | HuggingFace model ID |
| `CB_AGENT_MODE` | `rag` | AI mode: `rag` (simple) or `langgraph` (agentic) |
| `CB_AGENT_MAX_ITERATIONS` | `10` | Max agent iterations in langgraph mode |

### Database & Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `CB_DATABASE_URL` | `sqlite:///./data/...` | PostgreSQL or SQLite connection string |
| `CB_SQLITE_URL` | — | Explicit SQLite URL (dev convenience) |
| `CB_CHROMA_PERSIST_DIR` | `./data/chroma_db` | ChromaDB storage directory |
| `CB_REDIS_URL` | — | Redis URL for caching, rate limiting, and pub/sub |

### Embeddings & Retrieval

| Variable | Default | Description |
|----------|---------|-------------|
| `CB_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformers model |
| `CB_EMBEDDING_DIMENSION` | `384` | Embedding vector dimension |
| `CB_CHUNK_SIZE` | `512` | Text chunk size for embeddings |
| `CB_CHUNK_OVERLAP` | `64` | Chunk overlap tokens |
| `CB_RETRIEVAL_TOP_K` | `8` | Number of chunks to retrieve |
| `CB_CONTEXT_MAX_TOKENS` | `3000` | Max context tokens for LLM |

### Auth & OAuth

| Variable | Default | Description |
|----------|---------|-------------|
| `CB_JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `CB_JWT_EXPIRE_MINUTES` | `1440` | Token expiry (default: 24 hours) |
| `CB_GOOGLE_CLIENT_ID` | — | Google OAuth client ID (optional) |
| `CB_DEV_MODE` | `1` | Enable development mode (relaxed security) |

---

## :building_construction: Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Frontend (React 19)                       │
│  Vite 7 · TypeScript · Tailwind CSS 4 · React Router 7          │
│  WebSocket hooks · Force-directed graphs · Recharts              │
└─────────────┬──────────────────────┬─────────────────────────────┘
              │ REST API             │ WebSocket
              ▼                      ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                            │
│  15 Routers · JWT Auth · Rate Limiting · CORS · Security Headers │
├──────────────────────────────────────────────────────────────────┤
│  Services Layer                                                   │
│  ┌─────────────┐ ┌───────────────┐ ┌──────────────────────────┐ │
│  │ RAG Pipeline │ │ LangGraph     │ │ LLM Service              │ │
│  │ (retrieval + │ │ Agent         │ │ (Ollama/Claude/Mistral)  │ │
│  │  generation) │ │ (multi-step)  │ │                          │ │
│  └──────┬──────┘ └───────┬───────┘ └──────────────────────────┘ │
│         │                │                                       │
│  ┌──────▼────────────────▼──────┐  ┌──────────────────────────┐ │
│  │ Embedding Service            │  │ Insight Engine            │ │
│  │ (SentenceTransformers)       │  │ Knowledge Graph Builder   │ │
│  └──────┬───────────────────────┘  │ Expert Routing            │ │
│         │                          └──────────────────────────┘ │
├─────────┼────────────────────────────────────────────────────────┤
│  Data   │                                                        │
│  ┌──────▼──────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐ │
│  │  ChromaDB   │  │ PostgreSQL │  │   Redis    │  │ Celery   │ │
│  │  (vectors)  │  │ (relational│  │ (cache,    │  │ (async   │ │
│  │             │  │  + SQLite) │  │  pub/sub)  │  │  tasks)  │ │
│  └─────────────┘  └────────────┘  └────────────┘  └──────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### Project Structure

```
collective-brain/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app, middleware, startup
│   │   ├── config.py              # Pydantic settings (CB_* env vars)
│   │   ├── dependencies.py        # Auth dependencies (get_current_user)
│   │   ├── models/                # SQLAlchemy ORM models (9 models)
│   │   │   ├── user.py            # User accounts
│   │   │   ├── member.py          # Team members
│   │   │   ├── artifact.py        # Ingested artifacts
│   │   │   ├── contribution.py    # Member contributions
│   │   │   ├── conversation.py    # AI conversations + messages
│   │   │   ├── discussion.py      # Discussion threads + messages
│   │   │   ├── room.py            # Chat rooms + messages
│   │   │   └── insight.py         # AI-generated insights
│   │   ├── schemas/               # Pydantic request/response models
│   │   ├── routers/               # API endpoints (15 routers)
│   │   │   ├── auth.py            # Register, login, Google OAuth
│   │   │   ├── query.py           # AI Q&A (RAG / LangGraph)
│   │   │   ├── members.py         # Team member CRUD
│   │   │   ├── ingest.py          # Data ingestion (7 source types)
│   │   │   ├── conversations.py   # Conversation management + sharing
│   │   │   ├── rooms.py           # Chat rooms + WebSocket
│   │   │   ├── discussions.py     # Discussion threads + WebSocket
│   │   │   ├── insights.py        # Dashboard, summaries, patterns
│   │   │   ├── graph.py           # Knowledge graph endpoints
│   │   │   ├── analytics.py       # Activity, health, trends
│   │   │   ├── artifacts.py       # Ingested source management
│   │   │   ├── search.py          # Cross-entity search (SQL + semantic)
│   │   │   ├── slack.py           # Slack OAuth integration
│   │   │   ├── github_webhooks.py # GitHub webhook handlers
│   │   │   ├── expert_routing.py  # Expert recommendation
│   │   │   └── health.py          # Health check
│   │   ├── services/              # Business logic (20+ services)
│   │   │   ├── rag_pipeline.py    # RAG Q&A pipeline
│   │   │   ├── agent_pipeline.py  # LangGraph agentic pipeline
│   │   │   ├── agent_tools.py     # Agent tool definitions
│   │   │   ├── llm_service.py     # Multi-provider LLM abstraction
│   │   │   ├── embedding_service.py
│   │   │   ├── vector_store.py    # ChromaDB operations
│   │   │   ├── insight_engine.py  # Insight generation
│   │   │   ├── memory_graph.py    # Knowledge graph builder
│   │   │   ├── auth_service.py    # JWT + password hashing
│   │   │   ├── redis_service.py   # Redis cache + rate limiting
│   │   │   └── circuit_breaker.py # Resilience patterns
│   │   ├── ingestion/             # Data connectors (7 source types)
│   │   └── db/                    # Database setup + session management
│   ├── alembic/                   # Database migrations
│   ├── tests/                     # Pytest test suites
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/                 # 15+ route pages
│   │   ├── components/            # 30+ reusable UI components
│   │   ├── hooks/                 # React hooks (auth, chat, rooms, etc.)
│   │   │   ├── useAuth.tsx        # Auth context + provider
│   │   │   ├── useChat.ts         # AI conversation hook
│   │   │   ├── useDiscussion.ts   # Discussion WebSocket hook
│   │   │   └── useRoom.ts        # Room WebSocket hook
│   │   ├── api/client.ts          # API client with auth interceptors
│   │   ├── types/index.ts         # TypeScript type definitions
│   │   ├── App.tsx                # Router + layout
│   │   └── main.tsx               # Entry point
│   ├── vite.config.ts
│   ├── package.json
│   └── tsconfig.json
├── .github/workflows/ci.yml       # CI/CD pipeline
├── docker-compose.yml              # Multi-service orchestration
├── Dockerfile                      # Production multi-stage build
├── render.yaml                     # Render.com deployment config
├── .env.example                    # Environment variable template
└── README.md
```

---

## :book: API Reference

All endpoints require JWT authentication (`Authorization: Bearer <token>`) unless marked as public.

### :closed_lock_with_key: Auth — `/api/auth`

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| `POST` | `/auth/register` | No | Create a new account |
| `POST` | `/auth/login` | No | Login and receive JWT |
| `POST` | `/auth/google` | No | Google OAuth login |
| `POST` | `/auth/password-reset` | No | Request password reset |
| `GET` | `/auth/me` | Yes | Get current user profile |
| `PUT` | `/auth/me` | Yes | Update profile |

### :robot: AI Q&A — `/api/query`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/query` | Ask a question (RAG or LangGraph mode) |

Supports conversation context, room-scoped queries, and returns source attribution with confidence scores.

### :busts_in_silhouette: Members — `/api/members`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/members` | List all team members |
| `GET` | `/members/{id}` | Get member with expertise details |
| `POST` | `/members` | Create a member |
| `PUT` | `/members/{id}` | Update a member |
| `DELETE` | `/members/{id}` | Delete a member |

### :inbox_tray: Ingest — `/api/ingest`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/ingest/git` | Ingest a git repository |
| `POST` | `/ingest/markdown` | Ingest a markdown directory |
| `POST` | `/ingest/documents` | Upload PDF/DOCX/TXT files |
| `POST` | `/ingest/file` | Upload a single file |
| `POST` | `/ingest/slack` | Import Slack export archive |
| `POST` | `/ingest/discord` | Import Discord export |
| `POST` | `/ingest/tasks` | Import task JSON |

### :speech_balloon: Conversations — `/api/conversations`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/conversations` | List conversations |
| `GET` | `/conversations/{id}` | Get conversation with messages |
| `DELETE` | `/conversations/{id}` | Delete a conversation |
| `POST` | `/conversations/{id}/share` | Share with other users |
| `GET` | `/conversations/{id}/participants` | List participants |

### :house: Rooms — `/api/rooms`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/rooms` | List rooms |
| `POST` | `/rooms` | Create a room |
| `GET` | `/rooms/{id}` | Get room details + messages |
| `PUT` | `/rooms/{id}` | Update room settings |
| `POST` | `/rooms/{id}/members` | Add members to room |
| `DELETE` | `/rooms/{id}/members/{uid}` | Remove a member |
| `POST` | `/rooms/{id}/messages` | Send a message |
| `POST` | `/rooms/{id}/ai-query` | Ask AI in room context |
| `WS` | `/rooms/ws/{id}` | Real-time room chat |

### :left_speech_bubble: Discussions — `/api/discussions`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/discussions` | List discussion threads |
| `POST` | `/discussions` | Create a thread |
| `GET` | `/discussions/{id}` | Get thread with messages |
| `POST` | `/discussions/{id}/messages` | Post a message |
| `PUT` | `/discussions/{id}/messages/{mid}` | Edit a message |
| `DELETE` | `/discussions/{id}/messages/{mid}` | Delete a message |
| `WS` | `/discussions/ws/{id}` | Real-time thread updates |

### Additional Routers

| Router | Prefix | Description |
|--------|--------|-------------|
| Insights | `/api/insights` | Dashboard data, weekly summaries, pattern detection |
| Graph | `/api/graph` | Knowledge graph nodes/edges, mind maps, heatmaps |
| Analytics | `/api/analytics` | Activity timeline, health metrics, topic trends |
| Artifacts | `/api/artifacts` | Manage ingested sources and metadata |
| Search | `/api/search` | Cross-entity search (SQL full-text + semantic) |
| Slack | `/api/slack` | Slack OAuth flow and digest configuration |
| GitHub | `/api/github` | GitHub webhook receiver with signature verification |
| Experts | `/api/experts` | Expert recommendation for questions |
| Health | `/health` | Health check (public) |

Full interactive API docs are available at `/docs` (Swagger UI) and `/redoc` (ReDoc) when the backend is running.

---

## :hammer_and_wrench: Development

### LLM Providers

#### Ollama (Local, Default)

Free, runs locally with no API key required.

```bash
# Install Ollama from https://ollama.com
ollama pull llama3.1:8b
```

Set `CB_LLM_PROVIDER=ollama` in your `.env`.

#### Claude (Anthropic)

```bash
CB_LLM_PROVIDER=claude
CB_CLAUDE_API_KEY=sk-ant-...
```

#### Mistral / HuggingFace Inference

```bash
CB_LLM_PROVIDER=mistral
CB_MISTRAL_API_KEY=hf_...
```

Uses the HuggingFace Inference API with a configurable model (default: `Qwen/Qwen2.5-72B-Instruct`).

### Code Style

- **Backend**: Linted with [Ruff](https://docs.astral.sh/ruff/) (`ruff check` + `ruff format`)
- **Frontend**: Linted with ESLint + TypeScript strict mode
- Pre-commit checks run via CI on all PRs

### Database Migrations

```bash
cd backend

# Create a new migration after model changes
alembic revision --autogenerate -m "description of changes"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

---

## :test_tube: Testing

The CI pipeline runs three categories of backend tests and frontend checks.

```bash
# Backend — activate virtual environment first
cd backend
source .venv/bin/activate

# Unit tests
pytest tests/unit/ -v --tb=short

# Integration tests
pytest tests/integration/ -v --tb=short

# Security tests
pytest tests/security/ -v --tb=short

# All tests with coverage
pytest tests/ -v --cov=app --cov-report=term-missing

# Frontend
cd frontend
npm run lint          # ESLint
npx tsc --noEmit      # Type checking
npm run build         # Build verification
```

### CI Pipeline

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push to `main`/`develop` and on all PRs:

1. **Backend Lint** — Ruff check + format verification
2. **Backend Tests** — Unit, integration, and security tests (with Redis service)
3. **Frontend Lint** — ESLint + TypeScript type checking
4. **Frontend Build** — Production build verification
5. **Docker Build** — Full Docker image build test

---

## :whale: Deployment

### Docker Compose (Self-Hosted)

Full production deployment with PostgreSQL, Redis, backend, frontend, and Celery worker.

```bash
# Configure secrets
cp .env.example .env
# Set CB_POSTGRES_PASSWORD, CB_REDIS_PASSWORD, CB_JWT_SECRET

# Build and start
docker-compose up -d --build

# View logs
docker-compose logs -f backend

# Stop
docker-compose down
```

Services exposed:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### Render.com

The project includes a `render.yaml` Blueprint for one-click deployment on [Render](https://render.com).

1. Fork this repository
2. Create a new **Blueprint** on Render, pointing to your fork
3. Render will auto-detect `render.yaml` and provision the service
4. Set `CB_MISTRAL_API_KEY` (or your preferred LLM provider key) in the Render dashboard
5. The app deploys with SQLite and a 1 GB persistent disk

### HuggingFace Spaces

The repository is configured for deployment on [HuggingFace Spaces](https://huggingface.co/spaces) using the Docker SDK.

1. Create a new Space with the **Docker** SDK
2. Push this repository to the Space
3. The `Dockerfile` at the root handles the multi-stage build
4. Configure secrets (`CB_JWT_SECRET`, `CB_MISTRAL_API_KEY`, etc.) in the Space settings

### Production Checklist

- [ ] Set strong, unique values for `CB_JWT_SECRET`, `CB_POSTGRES_PASSWORD`, and `CB_REDIS_PASSWORD`
- [ ] Set `CB_DEV_MODE=0` to enable strict security
- [ ] Configure CORS origins for your domain
- [ ] Set up TLS/HTTPS termination (via reverse proxy or hosting platform)
- [ ] Configure a persistent volume for ChromaDB data
- [ ] Set up log aggregation and monitoring
- [ ] Review rate limiting thresholds for your expected traffic

---

## :shield: Security

Collective Brain implements multiple layers of security:

- **Authentication** — JWT tokens with bcrypt password hashing; Google OAuth support
- **CORS** — Configurable origin restriction (strict in production)
- **Security Headers** — `X-Frame-Options`, `Content-Security-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options`
- **Rate Limiting** — Per-endpoint limits on registration, login, queries, and password reset (Redis-backed)
- **File Upload Protection** — ZIP bomb detection and file size limits
- **WebSocket Limits** — Per-user connection caps to prevent resource exhaustion
- **Webhook Verification** — GitHub webhook signature verification (`X-Hub-Signature-256`)
- **Request Tracing** — Unique request IDs for debugging and audit trails
- **Circuit Breaker** — Resilience pattern for external service calls (LLM providers, OAuth)
- **Input Validation** — Pydantic schema validation on all request bodies

### Reporting Vulnerabilities

If you discover a security vulnerability, please report it responsibly by opening a private issue or contacting the maintainers directly. Do not open a public issue for security vulnerabilities.

---

## :handshake: Contributing

Contributions are welcome! Here is how to get started:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/your-feature`
3. **Make** your changes with tests
4. **Run** the linters and test suite:
   ```bash
   # Backend
   cd backend && ruff check . && ruff format --check . && pytest tests/ -v

   # Frontend
   cd frontend && npm run lint && npx tsc --noEmit
   ```
5. **Commit** your changes: `git commit -m 'Add your feature'`
6. **Push** to your branch: `git push origin feature/your-feature`
7. **Open** a Pull Request against `main`

### Development Guidelines

- Follow existing code style (Ruff for Python, ESLint for TypeScript)
- Add tests for new features and bug fixes
- Update Pydantic schemas when modifying API contracts
- Create Alembic migrations for any database model changes
- Keep PRs focused — one feature or fix per PR

---

## :page_facing_up: License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

<div align="center">

Built with :purple_heart: using FastAPI, React, and the power of RAG

[Back to Top](#brain-collective-brain)

</div>
