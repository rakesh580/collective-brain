# Collective Brain

An AI-powered team knowledge platform that ingests your team's work (git repos, documents, markdown files), builds a knowledge graph of members, contributions, and insights, and lets your team collaborate through real-time chat rooms, shared AI conversations, and discussion threads.

## Features

- **AI-Powered Q&A** — Ask questions about your team's knowledge base using RAG (Retrieval-Augmented Generation) or an agentic LangGraph pipeline
- **Team Member Profiles** — Auto-discovered from ingested data or manually created, with expertise tags, strengths, and contribution tracking
- **Real-Time Rooms** — WebSocket-powered group chat rooms with typing indicators, presence tracking, and in-room AI queries
- **Shared AI Conversations** — Share AI Q&A conversations with team members, with full message attribution
- **Discussion Threads** — Async threaded discussions attachable to members, insights, or standalone topics with real-time WebSocket updates
- **Knowledge Graph** — Visual graph of relationships between members, artifacts, and insights
- **Data Ingestion** — Ingest git repositories, markdown directories, and document files to build your knowledge base
- **Insight Engine** — AI-generated insights from your team's contributions and knowledge patterns
- **Analytics Dashboard** — Team activity metrics and contribution analytics
- **JWT Authentication** — Secure user accounts with registration, login, and profile management
- **Multi-LLM Support** — Switch between Ollama (local), Claude (Anthropic), or Mistral/HuggingFace inference

## Tech Stack

### Backend
- **FastAPI** — Python async web framework
- **SQLAlchemy** — ORM with SQLite (dev) or PostgreSQL (production) support
- **ChromaDB** — Vector database for semantic search
- **LangGraph** — Agentic AI pipeline (optional)
- **Sentence Transformers** — Local embedding generation
- **WebSocket** — Real-time communication for rooms and discussions
- **Celery + Redis** — Background task queue (optional)
- **Passlib + python-jose** — Password hashing and JWT tokens

### Frontend
- **React 18** — UI library
- **TypeScript** — Type-safe development
- **Vite** — Fast build tool
- **Tailwind CSS 4** — Utility-first styling
- **React Router** — Client-side routing
- **WebSocket** — Real-time updates

### Infrastructure
- **Docker Compose** — Container orchestration (PostgreSQL, Redis, Backend, Frontend, Celery Worker)

## Project Structure

```
collective-brain/
├── backend/
│   ├── app/
│   │   ├── config.py              # Settings (pydantic-settings, CB_* env vars)
│   │   ├── main.py                # FastAPI app entry point
│   │   ├── dependencies.py        # Auth dependencies (get_current_user)
│   │   ├── db/
│   │   │   └── database.py        # SQLAlchemy engine, session, migrations
│   │   ├── models/                # SQLAlchemy models
│   │   │   ├── user.py            # User accounts
│   │   │   ├── member.py          # Team members
│   │   │   ├── artifact.py        # Ingested artifacts (repos, docs)
│   │   │   ├── contribution.py    # Member contributions
│   │   │   ├── conversation.py    # AI conversations + messages
│   │   │   ├── discussion.py      # Discussion threads + messages
│   │   │   ├── room.py            # Chat rooms + messages
│   │   │   └── insight.py         # AI-generated insights
│   │   ├── routers/               # API endpoints
│   │   │   ├── auth.py            # Register, login, profile
│   │   │   ├── query.py           # AI Q&A (RAG / Agent)
│   │   │   ├── members.py         # Member CRUD
│   │   │   ├── conversations.py   # Conversation management + sharing
│   │   │   ├── discussions.py     # Discussion threads + WebSocket
│   │   │   ├── rooms.py           # Chat rooms + WebSocket
│   │   │   ├── ingest.py          # Data ingestion (git, markdown, docs)
│   │   │   ├── insights.py        # Insight generation + retrieval
│   │   │   ├── graph.py           # Knowledge graph data
│   │   │   ├── analytics.py       # Team analytics
│   │   │   ├── search.py          # Full-text + semantic search
│   │   │   ├── artifacts.py       # Artifact management
│   │   │   └── health.py          # Health check endpoint
│   │   ├── services/              # Business logic
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
│   │   │   ├── circuit_breaker.py # Resilience patterns
│   │   │   └── task_queue.py      # Celery task definitions
│   │   └── schemas/               # Pydantic request/response models
│   │       ├── requests.py
│   │       └── responses.py
│   ├── tests/
│   │   └── collaboration_test.py  # Multi-user collaboration test suite
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/client.ts          # API client with auth
│   │   ├── hooks/                 # React hooks
│   │   │   ├── useAuth.tsx        # Auth context + provider
│   │   │   ├── useChat.ts         # AI conversation hook
│   │   │   ├── useDiscussion.ts   # Discussion WebSocket hook
│   │   │   └── useRoom.ts         # Room WebSocket hook
│   │   ├── pages/                 # Route pages
│   │   │   ├── LoginPage.tsx
│   │   │   ├── RegisterPage.tsx
│   │   │   ├── ChatPage.tsx
│   │   │   ├── MembersPage.tsx
│   │   │   ├── RoomsPage.tsx
│   │   │   ├── RoomChatPage.tsx
│   │   │   ├── DiscussionsPage.tsx
│   │   │   ├── GraphPage.tsx
│   │   │   ├── IngestPage.tsx
│   │   │   ├── AnalyticsPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   └── SettingsPage.tsx
│   │   ├── components/            # Reusable UI components
│   │   ├── types/index.ts         # TypeScript type definitions
│   │   ├── App.tsx                # Router + layout
│   │   └── main.tsx               # Entry point
│   ├── Dockerfile
│   ├── vite.config.ts
│   ├── package.json
│   └── tsconfig.json
├── docker-compose.yml
├── .gitignore
├── .env.example                   # Docker Compose env vars
└── README.md
```

## Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- Node.js 18+
- (Optional) Ollama for local LLM — [Install Ollama](https://ollama.com)

### Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings (API keys, etc.)

# Run the server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run the dev server (proxies API calls to backend on port 8000)
npm run dev
```

The app will be available at `http://localhost:5173`.

### First Steps
1. Open `http://localhost:5173` — you'll be redirected to the registration page
2. Create an account
3. Navigate to **Ingest** to import a git repo or markdown files
4. Go to **Chat** to ask AI questions about your team's knowledge
5. Create a **Room** to collaborate in real-time with teammates

## Quick Start (Docker)

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your passwords and API keys

# Start all services
docker-compose up -d

# The app will be available at:
# - Frontend: http://localhost:3000
# - Backend API: http://localhost:8000
# - PostgreSQL: localhost:5432
# - Redis: localhost:6379
```

## Environment Variables

All backend settings use the `CB_` prefix and are loaded via pydantic-settings.

| Variable | Default | Description |
|----------|---------|-------------|
| `CB_LLM_PROVIDER` | `ollama` | LLM provider: `ollama`, `claude`, or `mistral` |
| `CB_CLAUDE_API_KEY` | _(empty)_ | Anthropic API key (required if provider=claude) |
| `CB_CLAUDE_MODEL` | `claude-sonnet-4-20250514` | Claude model ID |
| `CB_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `CB_OLLAMA_MODEL` | `llama3.1:8b` | Ollama model name |
| `CB_MISTRAL_API_KEY` | _(empty)_ | HuggingFace token (required if provider=mistral) |
| `CB_MISTRAL_MODEL` | `Qwen/Qwen2.5-72B-Instruct` | HuggingFace model ID |
| `CB_AGENT_MODE` | `rag` | AI mode: `rag` (simple) or `langgraph` (agentic) |
| `CB_AGENT_MAX_ITERATIONS` | `10` | Max agent iterations (langgraph mode) |
| `CB_JWT_SECRET` | `dev-secret-...` | JWT signing secret (**change in production**) |
| `CB_JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `CB_JWT_EXPIRE_MINUTES` | `1440` | Token expiry (24 hours) |
| `CB_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence transformer model |
| `CB_EMBEDDING_DIMENSION` | `384` | Embedding vector dimension |
| `CB_DATABASE_URL` | `sqlite:///./data/...` | Database URL (SQLite or PostgreSQL) |
| `CB_CHROMA_PERSIST_DIR` | `./data/chroma_db` | ChromaDB storage directory |
| `CB_REDIS_URL` | _(empty)_ | Redis URL (optional, for caching/rate limiting) |
| `CB_CHUNK_SIZE` | `512` | Text chunk size for embeddings |
| `CB_CHUNK_OVERLAP` | `64` | Chunk overlap tokens |
| `CB_RETRIEVAL_TOP_K` | `8` | Number of chunks to retrieve |
| `CB_CONTEXT_MAX_TOKENS` | `3000` | Max context tokens for LLM |

## API Endpoints

All endpoints require JWT authentication (via `Authorization: Bearer <token>` header) unless noted.

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Register new user (no auth) |
| POST | `/auth/login` | Login (no auth) |
| GET | `/auth/me` | Get current user profile |
| PUT | `/auth/me` | Update profile |
| GET | `/auth/users` | List all users |

### AI Query
| Method | Path | Description |
|--------|------|-------------|
| POST | `/query` | Ask an AI question (RAG or Agent) |

### Members
| Method | Path | Description |
|--------|------|-------------|
| GET | `/members` | List all team members |
| GET | `/members/{id}` | Get member details |
| POST | `/members` | Create a member |
| PUT | `/members/{id}` | Update a member |
| DELETE | `/members/{id}` | Delete a member |

### Conversations
| Method | Path | Description |
|--------|------|-------------|
| GET | `/conversations` | List conversations |
| GET | `/conversations/{id}` | Get conversation with messages |
| DELETE | `/conversations/{id}` | Delete a conversation |
| POST | `/conversations/{id}/share` | Share with other users |
| GET | `/conversations/{id}/participants` | List participants |

### Discussions
| Method | Path | Description |
|--------|------|-------------|
| GET | `/discussions` | List discussion threads |
| POST | `/discussions` | Create a thread |
| GET | `/discussions/{id}` | Get thread with messages |
| POST | `/discussions/{id}/messages` | Post a message |
| PUT | `/discussions/{id}/messages/{mid}` | Edit a message |
| DELETE | `/discussions/{id}/messages/{mid}` | Delete a message |
| WS | `/discussions/ws/{id}` | Real-time thread updates |

### Rooms
| Method | Path | Description |
|--------|------|-------------|
| GET | `/rooms` | List rooms |
| POST | `/rooms` | Create a room |
| GET | `/rooms/{id}` | Get room details + messages |
| PUT | `/rooms/{id}` | Update room |
| POST | `/rooms/{id}/members` | Add members |
| DELETE | `/rooms/{id}/members/{uid}` | Remove member |
| POST | `/rooms/{id}/messages` | Send a message |
| POST | `/rooms/{id}/ai-query` | Ask AI in room context |
| WS | `/rooms/ws/{id}` | Real-time room chat |

### Data Ingestion
| Method | Path | Description |
|--------|------|-------------|
| POST | `/ingest/git` | Ingest a git repository |
| POST | `/ingest/markdown` | Ingest markdown directory |
| POST | `/ingest/documents` | Upload document files |
| POST | `/ingest/file` | Upload a single file |

### Other
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (no auth) |
| GET | `/insights` | List AI-generated insights |
| POST | `/insights/generate` | Generate new insights |
| GET | `/graph/data` | Knowledge graph data |
| GET | `/analytics/overview` | Team analytics |
| GET | `/search` | Full-text + semantic search |

## LLM Providers

### Ollama (Local, Default)
Free, runs locally. Install from [ollama.com](https://ollama.com), then:
```bash
ollama pull llama3.1:8b
```
Set `CB_LLM_PROVIDER=ollama` in your `.env`.

### Claude (Anthropic)
Set `CB_LLM_PROVIDER=claude` and `CB_CLAUDE_API_KEY=your-api-key`.

### Mistral / HuggingFace Inference
Set `CB_LLM_PROVIDER=mistral` and `CB_MISTRAL_API_KEY=your-hf-token`.
Uses HuggingFace Inference API with configurable model.

## Running Tests

```bash
cd backend

# Activate virtual environment
source .venv/bin/activate

# Run the collaboration test suite (requires backend running on port 8000)
python tests/collaboration_test.py
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License.
