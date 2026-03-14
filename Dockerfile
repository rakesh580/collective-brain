# ── Stage 1: Build Frontend ──────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .

# All backend routes are under /api prefix to avoid collision with SPA routes
ENV VITE_API_BASE="/api"
# Limit Node.js memory for HuggingFace cpu-basic (2GB RAM)
ENV NODE_OPTIONS="--max-old-space-size=512"
RUN npm run build

# ── Stage 2: Backend + Static Files ─────────────────────────
FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2 and git ingestion
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev git \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first (saves ~1.5GB vs CUDA version)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Copy built frontend into static/ directory (served by FastAPI)
COPY --from=frontend-build /app/dist ./static

# Create data directories:
# /data  — HuggingFace Spaces persistent volume (survives container restarts)
# /app/data — fallback for local Docker runs
RUN mkdir -p /data/chroma_db /app/data/chroma_db \
    && chmod -R 777 /data /app/data

# Point SQLite + ChromaDB to HF persistent volume by default.
# These can be overridden via Space settings or .env for other platforms.
ENV CB_SQLITE_URL="sqlite:////data/collective_brain.db"
ENV CB_DATABASE_URL=""
ENV CB_CHROMA_PERSIST_DIR="/data/chroma_db"

# LLM Configuration — uses HuggingFace Inference API (free tier)
# CB_MISTRAL_API_KEY falls back to HF_TOKEN (auto-set on HF Spaces)
ENV CB_LLM_PROVIDER="mistral"
ENV CB_MISTRAL_MODEL="Qwen/Qwen2.5-72B-Instruct"
ENV CB_AGENT_MODE="rag"
ENV CB_DEV_MODE="1"

# HF Spaces uses port 7860, Render uses 8000
EXPOSE 7860 8000

# Single worker: WebSocket connections are process-local and don't
# work across multiple workers without a Redis pub/sub layer.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
