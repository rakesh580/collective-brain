# Collective Brain - Development Guide

## 1. Prerequisites

| Tool | Version | Required | Notes |
|------|---------|----------|-------|
| Python | 3.11+ | Yes | Backend runtime |
| Node.js | 18+ (20 recommended) | Yes | Frontend build tooling |
| npm | 9+ | Yes | Comes with Node.js |
| Docker | 20+ | Optional | For containerized development |
| Docker Compose | v2+ | Optional | Multi-service orchestration |
| Ollama | Latest | Optional | Local LLM inference (default provider) |
| PostgreSQL | 16+ | Optional | Production database (SQLite used by default) |
| Redis | 7+ | Optional | Pub/sub and caching (in-memory fallback available) |

---

## 2. Local Setup

### 2.1 Clone the Repository

```bash
git clone https://github.com/<your-org>/collective-brain.git
cd collective-brain
```

### 2.2 Backend Setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install CPU-only PyTorch first (saves ~1.5GB)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install all dependencies
pip install -r requirements.txt

# Copy environment template and customize
cp .env.example .env
# Edit .env with your settings (see Environment Variables section below)

# Run the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will be available at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

### 2.3 Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

The frontend will be available at `http://localhost:5173` with hot module replacement. It proxies API requests to the backend at `http://localhost:8000`.

### 2.4 Database Setup

**SQLite (default):** No setup required. The database file is auto-created at `backend/data/collective_brain.db` on first startup.

**PostgreSQL (optional):**
```bash
# Using Docker
docker run -d --name cb-postgres \
  -e POSTGRES_DB=collective_brain \
  -e POSTGRES_USER=cb_user \
  -e POSTGRES_PASSWORD=your_password \
  -p 5432:5432 \
  postgres:16-alpine

# Set in your .env
CB_DATABASE_URL=postgresql://cb_user:your_password@localhost:5432/collective_brain
```

### 2.5 Redis (Optional)

```bash
# Using Docker
docker run -d --name cb-redis \
  -p 6379:6379 \
  redis:7-alpine

# Set in your .env
CB_REDIS_URL=redis://localhost:6379/0
```

Without Redis, the application falls back to in-memory pub/sub and caching. This works for single-process development but does not support multi-worker deployments.

### 2.6 LLM Provider Setup

**Ollama (default - local, free):**
```bash
# Install Ollama from https://ollama.com
ollama pull llama3.1:8b

# No .env changes needed (ollama is the default provider)
```

**Claude (Anthropic API):**
```bash
# Set in your .env
CB_LLM_PROVIDER=claude
CB_CLAUDE_API_KEY=sk-ant-...
```

**Mistral / HuggingFace Inference:**
```bash
# Set in your .env
CB_LLM_PROVIDER=mistral
CB_MISTRAL_API_KEY=hf_...
```

---

## 3. Environment Variables

All environment variables use the `CB_` prefix. They can be set in a `.env` file in the `backend/` directory.

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `CB_LLM_PROVIDER` | LLM provider: `claude`, `ollama`, or `mistral` | `ollama` | No |
| `CB_CLAUDE_API_KEY` | Anthropic API key | `""` | If using Claude |
| `CB_CLAUDE_MODEL` | Claude model name | `claude-sonnet-4-20250514` | No |
| `CB_OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` | No |
| `CB_OLLAMA_MODEL` | Ollama model name | `llama3.1:8b` | No |
| `CB_MISTRAL_API_KEY` | Mistral/HuggingFace API key (falls back to `HF_TOKEN`) | `""` | If using Mistral |
| `CB_MISTRAL_MODEL` | Mistral model name | `Qwen/Qwen2.5-72B-Instruct` | No |
| `CB_AGENT_MODE` | Agent mode: `langgraph` (multi-step) or `rag` (single-step) | `rag` | No |
| `CB_AGENT_MAX_ITERATIONS` | Maximum LangGraph agent iterations | `10` | No |
| `CB_JWT_SECRET` | JWT signing secret (auto-generated if empty) | `""` | Production |
| `CB_JWT_ALGORITHM` | JWT signing algorithm | `HS256` | No |
| `CB_JWT_EXPIRE_MINUTES` | JWT token expiry in minutes | `30` | No |
| `CB_GOOGLE_CLIENT_ID` | Google OAuth client ID | `""` | If using Google OAuth |
| `CB_EMBEDDING_MODEL` | SentenceTransformers model name | `all-MiniLM-L6-v2` | No |
| `CB_EMBEDDING_DIMENSION` | Embedding vector dimensions | `384` | No |
| `CB_CHROMA_PERSIST_DIR` | ChromaDB storage directory | `./data/chroma_db` | No |
| `CB_DATABASE_URL` | Database connection string (PostgreSQL or SQLite) | `""` | No |
| `CB_SQLITE_URL` | SQLite fallback URL (used when `DATABASE_URL` is empty) | `sqlite:///./data/collective_brain.db` | No |
| `CB_DB_POOL_SIZE` | PostgreSQL connection pool size | `10` | No |
| `CB_DB_MAX_OVERFLOW` | PostgreSQL max overflow connections | `20` | No |
| `CB_DB_POOL_TIMEOUT` | PostgreSQL pool timeout (seconds) | `30` | No |
| `CB_DB_POOL_RECYCLE` | PostgreSQL connection recycle (seconds) | `1800` | No |
| `CB_REDIS_URL` | Redis connection URL | `""` | No |
| `CB_CHUNK_SIZE` | Text chunk size in tokens | `512` | No |
| `CB_CHUNK_OVERLAP` | Chunk overlap in tokens | `64` | No |
| `CB_RETRIEVAL_TOP_K` | Number of chunks to retrieve | `8` | No |
| `CB_CONTEXT_MAX_TOKENS` | Maximum context window tokens | `3000` | No |
| `CB_RATE_LIMIT_REQUESTS` | General rate limit (requests/minute) | `60` | No |
| `CB_RATE_LIMIT_AI_REQUESTS` | AI query rate limit (requests/minute/user) | `10` | No |
| `CB_SLACK_CLIENT_ID` | Slack app client ID | `""` | If using Slack |
| `CB_SLACK_CLIENT_SECRET` | Slack app client secret | `""` | If using Slack |
| `CB_SLACK_SIGNING_SECRET` | Slack request signing secret | `""` | If using Slack |
| `CB_GITHUB_WEBHOOK_SECRET` | GitHub webhook secret | `""` | If using GitHub |
| `CB_CORS_ORIGIN` | Additional allowed CORS origin | `""` | No |
| `CB_DEV_MODE` | Enable development mode | `"0"` | No |

---

## 4. Project Structure

```
collective-brain/
├── Dockerfile                  # Multi-stage build (frontend + backend)
├── docker-compose.yml          # 5-service stack (postgres, redis, backend, frontend, worker)
├── render.yaml                 # Render.com deployment config
├── docs/                       # Documentation
│   ├── ARCHITECTURE.md
│   └── DEVELOPMENT.md
│
├── backend/
│   ├── Dockerfile              # Backend-only Docker image
│   ├── requirements.txt        # Python dependencies
│   ├── pyproject.toml          # Project metadata, Ruff config, pytest config
│   ├── alembic.ini             # Alembic configuration
│   ├── alembic/
│   │   ├── env.py              # Migration environment setup
│   │   ├── script.py.mako      # Migration template
│   │   └── versions/           # Migration scripts
│   ├── data/                   # Runtime data (SQLite DB, ChromaDB, gitignored)
│   ├── tests/
│   │   ├── unit/               # Unit tests
│   │   ├── integration/        # Integration tests
│   │   └── security/           # Security tests
│   └── app/
│       ├── __init__.py
│       ├── main.py             # FastAPI app, lifespan, middleware, router mounting
│       ├── config.py           # Pydantic Settings with CB_ prefix
│       ├── dependencies.py     # FastAPI dependency injection helpers
│       ├── db/
│       │   └── database.py     # SQLAlchemy engine, session factory, init_db()
│       ├── models/
│       │   ├── __init__.py     # Re-exports all models for Alembic auto-detection
│       │   ├── user.py         # User (auth accounts)
│       │   ├── member.py       # Member (team members with aliases)
│       │   ├── contribution.py # Contribution (knowledge entries)
│       │   ├── conversation.py # Conversation (AI chat sessions)
│       │   ├── artifact.py     # Artifact (ingested sources)
│       │   ├── discussion.py   # Discussion (threaded forums)
│       │   ├── insight.py      # Insight (AI-generated patterns)
│       │   ├── room.py         # Room (collaborative spaces)
│       │   └── slack_integration.py  # SlackIntegration (OAuth tokens)
│       ├── schemas/
│       │   ├── requests.py     # Pydantic request models
│       │   └── responses.py    # Pydantic response models
│       ├── routers/
│       │   ├── analytics.py    # Analytics endpoints
│       │   ├── artifacts.py    # Artifact CRUD
│       │   ├── auth.py         # Auth (register, login, OAuth, password reset)
│       │   ├── conversations.py # Conversation history
│       │   ├── discussions.py  # Discussions + WebSocket
│       │   ├── expert_routing.py # Expert recommendations
│       │   ├── github_webhooks.py # GitHub webhook handler
│       │   ├── graph.py        # Knowledge graph endpoints
│       │   ├── health.py       # Health check
│       │   ├── ingest.py       # Ingestion endpoints
│       │   ├── insights.py     # Insights and freshness
│       │   ├── members.py      # Member CRUD
│       │   ├── query.py        # AI query (RAG + agent)
│       │   ├── rooms.py        # Rooms + WebSocket
│       │   ├── search.py       # Full-text and semantic search
│       │   └── slack.py        # Slack integration
│       ├── services/
│       │   ├── agent_pipeline.py      # LangGraph agent
│       │   ├── agent_tools.py         # Agent tool definitions
│       │   ├── auth_service.py        # JWT + bcrypt + Google OAuth
│       │   ├── circuit_breaker.py     # Circuit breaker pattern
│       │   ├── digest_service.py      # Slack digest generation
│       │   ├── embedding_service.py   # SentenceTransformers embeddings
│       │   ├── freshness_service.py   # Knowledge freshness tracking
│       │   ├── github_event_processor.py # GitHub event processing
│       │   ├── insight_engine.py      # AI insight generation
│       │   ├── llm_service.py         # Multi-provider LLM client
│       │   ├── memory_graph.py        # NetworkX knowledge graph
│       │   ├── prompts.py             # Prompt templates
│       │   ├── rag_pipeline.py        # RAG orchestration
│       │   ├── redis_service.py       # Redis client with fallback
│       │   ├── slack_event_processor.py # Slack event processing
│       │   ├── slack_service.py       # Slack API client
│       │   ├── task_queue.py          # Background task queue
│       │   ├── team_health_service.py # Team health metrics
│       │   └── vector_store.py        # ChromaDB vector store
│       └── ingestion/
│           ├── base.py                # BaseConnector abstract class
│           ├── chunker.py             # Text chunking logic
│           ├── registry.py            # Connector registry + factory
│           ├── git_connector.py       # Git repository connector
│           ├── markdown_connector.py  # Markdown file connector
│           ├── document_connector.py  # PDF/DOCX connector
│           ├── slack_connector.py     # Slack channel connector
│           ├── discord_connector.py   # Discord channel connector
│           └── task_connector.py      # Task tracker connector
│
└── frontend/
    ├── Dockerfile              # Nginx-based production image
    ├── nginx.conf              # Nginx config (SPA routing, API proxy)
    ├── package.json            # Dependencies and scripts
    ├── vite.config.ts          # Vite configuration
    ├── tsconfig.json           # TypeScript config
    ├── eslint.config.js        # ESLint flat config
    ├── index.html              # HTML entry point
    └── src/
        ├── main.tsx            # React entry point (Router, providers)
        ├── App.tsx             # Route definitions, code splitting, error boundaries
        ├── index.css           # Tailwind CSS imports
        ├── types/              # TypeScript type definitions
        │   └── index.ts        # Shared types for API responses
        ├── api/
        │   └── client.ts       # Centralized API client with JWT auth
        ├── hooks/
        │   ├── useAuth.tsx     # Authentication state and actions
        │   ├── useChat.ts      # AI chat state management
        │   ├── useRoom.ts      # Room membership and WebSocket
        │   ├── useDiscussion.ts # Discussion threads and WebSocket
        │   ├── useTheme.tsx    # Dark/light theme management
        │   └── useGoogleAuth.tsx # Google OAuth integration
        ├── pages/
        │   ├── DashboardPage.tsx    # Home dashboard
        │   ├── ChatPage.tsx         # AI chat interface
        │   ├── IngestPage.tsx       # Data ingestion UI
        │   ├── MembersPage.tsx      # Member list + detail view
        │   ├── GraphPage.tsx        # Knowledge graph (lazy-loaded)
        │   ├── AnalyticsPage.tsx    # Analytics dashboard (lazy-loaded)
        │   ├── TeamHealthPage.tsx   # Team health metrics (lazy-loaded)
        │   ├── RoomsPage.tsx        # Room listing
        │   ├── RoomChatPage.tsx     # Room chat (lazy-loaded)
        │   ├── DiscussionsPage.tsx  # Discussion threads (lazy-loaded)
        │   ├── SettingsPage.tsx     # User settings
        │   ├── LoginPage.tsx        # Login form
        │   ├── RegisterPage.tsx     # Registration form
        │   └── ForgotPasswordPage.tsx # Password reset
        ├── components/
        │   ├── ErrorBoundary.tsx          # Generic error boundary
        │   ├── FeatureErrorBoundary.tsx   # Per-feature error boundary
        │   ├── auth/                      # Auth-related components
        │   ├── chat/                      # Chat UI components
        │   ├── dashboard/                 # Dashboard widgets
        │   ├── discussions/               # Discussion UI components
        │   ├── graph/                     # Graph visualization
        │   ├── ingest/                    # Ingestion form components
        │   ├── insights/                  # Insight display components
        │   ├── integrations/              # Slack/GitHub integration UI
        │   ├── layout/                    # PageShell, sidebar, navbar
        │   ├── members/                   # Member list/detail components
        │   └── onboarding/               # Onboarding flow
        └── assets/                       # Static assets (images, icons)
```

---

## 5. Development Workflow

### 5.1 Backend: Adding a New Feature

1. **Define the model** (if new data is needed):
   ```python
   # backend/app/models/my_feature.py
   from sqlalchemy import Column, String, DateTime
   from app.db.database import Base

   class MyFeature(Base):
       __tablename__ = "my_features"
       id = Column(String, primary_key=True)
       name = Column(String, nullable=False)
   ```

2. **Register the model** in `backend/app/models/__init__.py`:
   ```python
   from app.models.my_feature import MyFeature  # noqa: F401
   ```

3. **Create a migration** (see Section 7 below).

4. **Add request/response schemas** in `backend/app/schemas/requests.py` and `responses.py`.

5. **Add the service** in `backend/app/services/my_feature_service.py`.

6. **Add the router** in `backend/app/routers/my_feature.py`:
   ```python
   from fastapi import APIRouter
   router = APIRouter()

   @router.get("/")
   async def list_features():
       ...
   ```

7. **Mount the router** in `backend/app/main.py`:
   ```python
   from app.routers import my_feature
   app.include_router(my_feature.router, prefix="/api/my-feature", tags=["my-feature"])
   ```

### 5.2 Frontend: Adding a New Page

1. **Create the page component** in `frontend/src/pages/MyFeaturePage.tsx`.

2. **Add the route** in `frontend/src/App.tsx`:
   ```tsx
   // If heavy, use lazy loading:
   const MyFeaturePage = lazy(() => import("./pages/MyFeaturePage"));

   // Inside the protected routes:
   <Route path="/my-feature" element={guarded(<MyFeaturePage />, "My Feature")} />
   ```

3. **Add API methods** in `frontend/src/api/client.ts`:
   ```typescript
   getMyFeatures: (signal?: AbortSignal) =>
     request<MyFeature[]>("/my-feature", { signal }),
   ```

4. **Add TypeScript types** in `frontend/src/types/index.ts`.

5. **Create a custom hook** (if complex state is needed) in `frontend/src/hooks/useMyFeature.ts`.

6. **Add navigation** in the sidebar component (`frontend/src/components/layout/`).

---

## 6. Adding a New Ingestion Source

### Step 1: Create the Connector

Create `backend/app/ingestion/my_source_connector.py`:

```python
from app.ingestion.base import BaseConnector


class MySourceConnector(BaseConnector):
    """Connector for ingesting data from MySource."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize source-specific configuration

    def fetch(self) -> list[dict]:
        """Fetch and return raw documents from the source.

        Each document should be a dict with:
        - content: str (the text content)
        - metadata: dict (author, date, source_path, etc.)
        """
        documents = []
        # ... fetch logic ...
        return documents
```

### Step 2: Register the Connector

Add it to `backend/app/ingestion/registry.py`:

```python
from app.ingestion.my_source_connector import MySourceConnector

_REGISTRY: dict[str, type[BaseConnector]] = {
    # ... existing connectors ...
    "my_source": MySourceConnector,
}
```

### Step 3: Add the Ingestion Router Endpoint

Add a new endpoint in `backend/app/routers/ingest.py`:

```python
@router.post("/my-source")
async def ingest_my_source(
    request: MySourceRequest,
    settings=Depends(get_settings),
):
    connector = get_connector("my_source", **request.dict())
    documents = connector.fetch()
    # ... chunk, embed, store ...
    return {"status": "ok", "chunks_created": len(chunks)}
```

### Step 4: Add Frontend UI

Add the source option in `frontend/src/components/ingest/` and wire it to the API client.

---

## 7. Database Migrations

Collective Brain uses [Alembic](https://alembic.sqlalchemy.org/) for database schema migrations.

### Generate a Migration

After modifying or adding SQLAlchemy models:

```bash
cd backend

# Auto-generate migration from model changes
alembic revision --autogenerate -m "add my_features table"
```

This creates a new file in `backend/alembic/versions/`. Review the generated migration to verify correctness.

### Apply Migrations

```bash
# Upgrade to the latest version
alembic upgrade head

# Upgrade one step
alembic upgrade +1

# Downgrade one step
alembic downgrade -1

# View current revision
alembic current

# View migration history
alembic history
```

### Important Notes

- Always review auto-generated migrations before applying. Alembic cannot detect all changes (e.g., column renames are detected as drop + add).
- For SQLite, some operations (like `ALTER TABLE DROP COLUMN`) are not supported. Use batch mode in migrations.
- Run migrations before deploying new code that depends on schema changes.

---

## 8. Testing

### Backend Tests

```bash
cd backend

# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest

# Run specific test suites
pytest tests/unit/ -v              # Unit tests
pytest tests/integration/ -v       # Integration tests
pytest tests/security/ -v          # Security tests

# Run with coverage
pytest --cov=app --cov-report=html

# Run a specific test file
pytest tests/unit/test_rag_pipeline.py -v

# Run with timeout (recommended)
pytest tests/ -v --timeout=60
```

### Frontend Checks

```bash
cd frontend

# Lint with ESLint
npm run lint

# Type checking
npx tsc --noEmit

# Build (catches compilation errors)
npm run build
```

---

## 9. Linting

### Backend: Ruff

The project uses [Ruff](https://docs.astral.sh/ruff/) for Python linting and formatting, configured in `backend/pyproject.toml`:

```bash
cd backend

# Check for lint errors
ruff check .

# Auto-fix lint errors
ruff check --fix .

# Check formatting
ruff format --check .

# Auto-format
ruff format .
```

**Ruff configuration highlights:**
- Target: Python 3.11
- Line length: 120 characters
- Enabled rule sets: `E` (pycodestyle errors), `W` (warnings), `F` (pyflakes), `I` (isort), `B` (bugbear), `S` (bandit security), `UP` (pyupgrade), `SIM` (simplify), `T20` (print statements)
- Ignored: `S101` (assert in tests), `S104` (bind to 0.0.0.0), `E501` (line length, handled by formatter)
- Per-file overrides: tests allow assert and hardcoded passwords; alembic allows unused imports

### Frontend: ESLint

Configured in `frontend/eslint.config.js` (flat config format):

```bash
cd frontend

# Run lint checks
npm run lint
```

Uses `eslint-plugin-react-hooks` and `eslint-plugin-react-refresh` for React-specific rules.

---

## 10. CI/CD Pipeline

The project uses GitHub Actions (`.github/workflows/ci.yml`) with 4 jobs:

### Job Dependency Graph

```
backend-lint ──> backend-test ──┐
                                ├──> docker-build
frontend-lint ──> frontend-build┘
```

### Jobs

| Job | Trigger | Steps |
|-----|---------|-------|
| **backend-lint** | Push to `main`/`develop`, PRs to `main` | Install Ruff, run `ruff check` and `ruff format --check` |
| **backend-test** | After backend-lint passes | Start Redis service, install dependencies (CPU PyTorch), run unit/integration/security tests with pytest |
| **frontend-lint** | Push to `main`/`develop`, PRs to `main` | `npm ci`, `npm run lint`, `npx tsc --noEmit` |
| **frontend-build** | After frontend-lint passes | `npm ci`, `npm run build` |
| **docker-build** | After backend-test and frontend-build pass | Build the full Docker image |

### CI Environment

- Python 3.11, Node.js 20
- Redis 7 service container for integration tests
- pip and npm caching for faster builds
- Test environment: `CB_JWT_SECRET=test-secret-for-ci-only`, `CB_LLM_PROVIDER=ollama`, `CB_DEV_MODE=0`

---

## 11. Common Issues

### SQLite WAL Mode

**Problem:** SQLite WAL (Write-Ahead Logging) files can grow large and data may be lost if the container is killed without graceful shutdown.

**Solution:** The application flushes the WAL checkpoint on shutdown (`PRAGMA wal_checkpoint(TRUNCATE)`). For Docker, always use `docker stop` (not `docker kill`) to allow graceful shutdown. In production, prefer PostgreSQL.

### ChromaDB Persistence

**Problem:** ChromaDB data disappears after container restart.

**Solution:** Ensure `CB_CHROMA_PERSIST_DIR` points to a persistent volume:
- Docker Compose: Uses the `backend_data` named volume
- Render.com: Persistent disk at `/app/data`
- HuggingFace Spaces: Enable "Persistent Storage" in Space settings; data is stored at `/data/chroma_db`

### Redis Fallback

**Problem:** Application works locally but WebSocket messages are not broadcast to all clients in production.

**Solution:** Redis is required for multi-worker WebSocket fan-out. Without Redis, the app falls back to in-memory pub/sub that only works within a single process. Set `CB_REDIS_URL` in production or use a single worker.

### CORS in Development

**Problem:** `403 Forbidden` or CORS errors when the frontend calls the backend.

**Solution:** The backend allows `http://localhost:5173` and `http://localhost:3000` by default. If using a different port, set `CB_CORS_ORIGIN` to your frontend URL. Vite's dev server proxies `/api` requests, so CORS usually is not an issue during local development.

### First Query Latency

**Problem:** The first AI query takes 5-10 seconds longer than subsequent queries.

**Solution:** The embedding model is pre-loaded at startup. If you see "Failed to pre-load embedding model" in logs, check that `sentence-transformers` is installed and the model can be downloaded. Subsequent queries use the cached model.

### JWT Token Invalidation on Restart

**Problem:** All users are logged out when the container restarts.

**Solution:** Set `CB_JWT_SECRET` explicitly in your environment. Without it, a random secret is generated at startup. On HuggingFace Spaces with persistent storage, the secret is automatically persisted to `/data/.cb_jwt_secret`.

### Port Conflicts

**Problem:** "Address already in use" when starting the backend.

**Solution:** The backend defaults to port 8000. Check for other processes: `lsof -i :8000`. Use a different port with `uvicorn app.main:app --port 8001`.

### Docker on Apple Silicon

**Problem:** Slow builds or runtime errors on ARM64 Macs.

**Solution:** The Dockerfile uses `python:3.11-slim` which supports multi-arch. CPU-only PyTorch is installed explicitly. If you encounter issues, try building with `--platform linux/amd64`.
