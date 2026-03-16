# Collective Brain - Deployment Guide

This guide covers all supported deployment methods for Collective Brain, from local development to production hosting.

---

## Table of Contents

- [Docker Compose (Recommended)](#docker-compose-recommended)
- [Production Docker Build](#production-docker-build)
- [Render.com Deployment](#rendercom-deployment)
- [HuggingFace Spaces](#huggingface-spaces)
- [Database Options](#database-options)
- [LLM Configuration](#llm-configuration)
- [Redis Configuration](#redis-configuration)
- [SSL / HTTPS](#ssl--https)
- [Monitoring](#monitoring)

---

## Docker Compose (Recommended)

Docker Compose is the easiest way to run Collective Brain with all services pre-configured.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (v20.10+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.0+)

### Setup

1. **Copy the environment file and set required variables:**

   ```bash
   cp .env.example .env
   ```

   Open `.env` and set the following required values:

   ```dotenv
   CB_POSTGRES_PASSWORD=your_secure_postgres_password
   CB_REDIS_PASSWORD=your_secure_redis_password
   CB_JWT_SECRET=your_random_jwt_secret_at_least_32_chars
   ```

2. **Configure your LLM provider** (see [LLM Configuration](#llm-configuration) for details):

   - **Ollama (local, free):** No API key needed. Ensure Ollama is running on the host or set `CB_OLLAMA_BASE_URL`.
   - **Claude API:** Set `CB_CLAUDE_API_KEY=sk-ant-...`
   - **Mistral API:** Set `CB_MISTRAL_API_KEY=your_mistral_key`

3. **Start all services:**

   ```bash
   docker-compose up -d
   ```

4. **Verify the deployment:**

   ```bash
   curl http://localhost:8000/api/health
   ```

   You should receive a JSON response indicating all services are healthy.

5. **Access the application:**

   - **Frontend:** [http://localhost:3000](http://localhost:3000)
   - **API:** [http://localhost:8000/api](http://localhost:8000/api)

### Services Overview

| Service    | Port | Description                        |
|------------|------|------------------------------------|
| `postgres` | 5432 | PostgreSQL database                |
| `redis`    | 6379 | Redis for caching and pub/sub      |
| `backend`  | 8000 | FastAPI application server         |
| `frontend` | 3000 | React/Vite frontend dev server     |
| `worker`   | ---  | Background task worker (no port)   |

### Stopping Services

```bash
docker-compose down
```

To also remove volumes (warning: deletes all data):

```bash
docker-compose down -v
```

---

## Production Docker Build

For production, Collective Brain uses a multi-stage Dockerfile that produces a single container serving both the API and the frontend SPA.

### How It Works

1. **Stage 1 (Frontend Build):** Installs Node.js dependencies, builds the React frontend into static assets.
2. **Stage 2 (Backend):** Copies the compiled static files into the backend container, which serves them alongside the API.

This means a single container serves both the API at `/api/*` and the SPA at all other routes.

### Building the Image

```bash
docker build -t collective-brain:latest .
```

### Running in Production

```bash
docker run -d \
  --name collective-brain \
  -p 8000:8000 \
  -e CB_JWT_SECRET="your_production_jwt_secret" \
  -e CB_DATABASE_URL="postgresql://user:pass@db-host:5432/collective_brain" \
  -e CB_REDIS_URL="redis://:password@redis-host:6379/0" \
  -e CB_CLAUDE_API_KEY="sk-ant-..." \
  -e CB_ENVIRONMENT="production" \
  -e CB_CORS_ORIGINS="https://yourdomain.com" \
  collective-brain:latest
```

### Production Environment Variables

| Variable             | Description                              | Required |
|----------------------|------------------------------------------|----------|
| `CB_JWT_SECRET`      | Secret key for JWT token signing         | Yes      |
| `CB_DATABASE_URL`    | PostgreSQL connection string             | Yes      |
| `CB_REDIS_URL`       | Redis connection string                  | No       |
| `CB_ENVIRONMENT`     | Set to `production`                      | Yes      |
| `CB_CORS_ORIGINS`    | Comma-separated allowed origins          | Yes      |
| `CB_CLAUDE_API_KEY`  | Claude API key (if using Claude)         | No       |
| `CB_MISTRAL_API_KEY` | Mistral API key (if using Mistral)       | No       |

### Health Checks

The container exposes a health check endpoint at `/api/health`. Configure your orchestrator to poll this endpoint:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

---

## Render.com Deployment

Render provides a straightforward platform for deploying Collective Brain with a managed database.

### Using the Blueprint

The repository includes a `render.yaml` blueprint for one-click deployment:

1. Fork or push the repository to your GitHub account.
2. In the Render dashboard, go to **Blueprints** and connect your repository.
3. Render will detect `render.yaml` and create the required services automatically.

### Required Environment Variables

Set these in the Render dashboard under your service's **Environment** tab:

- `CB_JWT_SECRET` -- A random string (32+ characters) for signing tokens.
- `CB_DATABASE_URL` -- Provided automatically if using a Render PostgreSQL database.
- `CB_CLAUDE_API_KEY` or `CB_MISTRAL_API_KEY` -- Your chosen LLM provider key.

### Persistent Disk

If using SQLite or ChromaDB for vector storage, attach a persistent disk:

- **Mount path:** `/app/data`
- **Size:** 1 GB minimum (increase based on data volume)

This directory stores the SQLite database file and ChromaDB vector indices. Without a persistent disk, data is lost on every deploy.

### Free Tier Limitations

- Services spin down after 15 minutes of inactivity.
- Cold starts take 30-60 seconds.
- Limited to 750 hours/month of runtime.
- 512 MB RAM may be tight for large knowledge bases.
- Consider upgrading to a paid plan for production workloads.

---

## HuggingFace Spaces

Collective Brain can be deployed as a Docker Space on HuggingFace.

### Setup

1. Create a new Space on HuggingFace and select **Docker** as the SDK.
2. Push the repository to the Space's Git remote.
3. The Dockerfile will be detected and built automatically.

### CORS and Space ID

HuggingFace Spaces sets the `SPACE_ID` environment variable automatically (e.g., `your-username/collective-brain`). The application detects this and configures CORS origins accordingly, allowing the Space's iframe URL to make API requests.

No manual CORS configuration is needed when running on HuggingFace Spaces.

### Persistent Storage

HuggingFace Spaces provides a `/data` directory with persistent storage:

- SQLite database is stored at `/data/collective_brain.db`.
- ChromaDB indices are stored at `/data/chroma/`.
- This data survives container restarts and redeployments.

### JWT Secret Persistence

On HuggingFace Spaces, the application automatically generates and persists a JWT secret to `/data/.jwt_secret` on first run. This ensures that user sessions remain valid across container restarts. If you want to set your own secret, define the `CB_JWT_SECRET` environment variable in the Space settings, which takes priority over the auto-generated file.

### Environment Variables

Set secrets in the Space's **Settings > Repository secrets** panel:

- `CB_CLAUDE_API_KEY` or `CB_MISTRAL_API_KEY`
- `CB_JWT_SECRET` (optional; auto-generated if omitted)

---

## Database Options

### SQLite (Default)

SQLite is the default database and requires zero configuration.

- Data is stored in the `/data` directory (or the project root in development).
- WAL (Write-Ahead Logging) mode is enabled automatically for better concurrent read performance.
- Suitable for single-instance deployments and small to medium teams.
- No external database service needed.

```dotenv
# No configuration needed -- SQLite is used by default.
# Optionally specify a custom path:
CB_DATABASE_PATH=/data/collective_brain.db
```

### PostgreSQL (Recommended for Production)

PostgreSQL is recommended for production deployments, especially with multiple workers or high concurrency.

Set the database URL:

```dotenv
CB_DATABASE_URL=postgresql://username:password@hostname:5432/collective_brain
```

The application will automatically detect the PostgreSQL URL and use the appropriate database driver.

### Running Migrations

Database migrations are managed with Alembic. Run migrations after initial setup or after pulling updates:

```bash
# From the backend directory
alembic upgrade head
```

In Docker deployments, migrations run automatically on container startup.

---

## LLM Configuration

Collective Brain supports multiple LLM providers. Configure at least one to enable AI-powered features.

### Ollama (Local, Free)

Run LLMs locally with [Ollama](https://ollama.ai/):

1. Install Ollama on the host machine.
2. Pull a model: `ollama pull llama3` (or any supported model).
3. Configure the backend:

   ```dotenv
   CB_OLLAMA_BASE_URL=http://localhost:11434
   ```

   If running inside Docker, use the host's IP or `host.docker.internal`:

   ```dotenv
   CB_OLLAMA_BASE_URL=http://host.docker.internal:11434
   ```

### Claude (Anthropic)

Use Anthropic's Claude API for high-quality reasoning:

```dotenv
CB_CLAUDE_API_KEY=sk-ant-your-api-key-here
```

### Mistral

Use Mistral's API for a balance of speed and quality:

```dotenv
CB_MISTRAL_API_KEY=your-mistral-api-key-here
```

### Agent Modes

Collective Brain supports two agent modes that control how the AI processes queries:

| Mode        | Description                                                         | Best For                                |
|-------------|---------------------------------------------------------------------|-----------------------------------------|
| `rag`       | Retrieval-Augmented Generation. Lightweight, fast, low token usage. | Simple Q&A, factual lookups (default)   |
| `langgraph` | Agentic workflow with LangGraph. Multi-step reasoning and tools.    | Complex analysis, cross-referencing     |

Set the mode:

```dotenv
CB_AGENT_MODE=rag        # Default, lightweight
CB_AGENT_MODE=langgraph  # Agentic, complex reasoning
```

---

## Redis Configuration

Redis is optional but recommended for production deployments.

### Graceful Fallback

If Redis is not configured, the application falls back to in-memory alternatives:

- WebSocket pub/sub uses in-memory broadcast (single-process only).
- Rate limiting uses in-memory counters (resets on restart).
- Caching uses in-memory LRU cache.

This is fine for development and single-process deployments.

### When Redis Is Required

- **Multi-process WebSocket pub/sub:** If running multiple backend workers (e.g., with Gunicorn), Redis is required for WebSocket messages to reach all connected clients.
- **Rate limiting persistence:** Without Redis, rate limit counters reset whenever the server restarts.
- **Distributed caching:** Redis provides a shared cache across multiple workers.

### Configuration

```dotenv
CB_REDIS_URL=redis://:your_redis_password@localhost:6379/0
```

If your Redis instance does not require authentication:

```dotenv
CB_REDIS_URL=redis://localhost:6379/0
```

---

## SSL / HTTPS

In production, always serve Collective Brain behind a reverse proxy that handles SSL termination.

### Nginx Reverse Proxy Example

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # HSTS (Strict Transport Security)
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
```

### HSTS Auto-Enabled

When the application detects it is behind an HTTPS reverse proxy (via the `X-Forwarded-Proto` header), it automatically enables HSTS headers on API responses. No additional configuration is needed.

---

## Monitoring

### Health Endpoint

The `/api/health` endpoint returns the status of all services:

```bash
curl http://localhost:8000/api/health
```

Example response:

```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "llm_provider": "claude",
  "version": "1.0.0"
}
```

Use this endpoint for load balancer health checks, uptime monitors, and alerting.

### Request ID Tracing

Every API request is assigned a unique request ID, returned in the `X-Request-ID` response header. This ID is included in all log entries for that request, making it easy to trace a single request across services.

To trace a specific request:

```bash
# Make a request and note the request ID
curl -v http://localhost:8000/api/health 2>&1 | grep X-Request-ID

# Search logs for that request ID
docker-compose logs backend | grep "request_id=abc123"
```

### Structured Logging

The backend outputs structured JSON logs in production, which can be ingested by log aggregation tools such as Datadog, Loki, or ELK:

```json
{
  "timestamp": "2026-03-15T10:30:00Z",
  "level": "INFO",
  "request_id": "abc123",
  "method": "GET",
  "path": "/api/health",
  "status": 200,
  "duration_ms": 12
}
```

Set the log level with:

```dotenv
CB_LOG_LEVEL=INFO   # DEBUG, INFO, WARNING, ERROR, CRITICAL
```
