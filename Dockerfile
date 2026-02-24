# ── Stage 1: Build Frontend ──────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .

# Empty VITE_API_BASE so frontend calls backend routes directly
ENV VITE_API_BASE=""
RUN npm run build

# ── Stage 2: Backend + Static Files ─────────────────────────
FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2 and git ingestion
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev git \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Copy built frontend into static/ directory (served by FastAPI)
COPY --from=frontend-build /app/dist ./static

RUN mkdir -p /app/data/chroma_db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
