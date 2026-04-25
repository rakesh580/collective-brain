"""Prometheus metrics definitions for Collective Brain.

All metric objects live here so they are registered exactly once.
Import from this module in any service that needs to record a measurement.

Usage example:
    from app.services.metrics import LLM_LATENCY, INGESTION_CHUNKS

    with LLM_LATENCY.labels(provider="claude", org_id=org_id).time():
        result = await llm.generate(...)

    INGESTION_CHUNKS.labels(source_type="markdown", org_id=org_id).inc(chunk_count)
"""

from prometheus_client import Counter, Gauge, Histogram, Info

# ── HTTP layer (augments prometheus-fastapi-instrumentator's auto metrics) ──

HTTP_REQUESTS_TOTAL = Counter(
    "cb_http_requests_total",
    "Total HTTP requests handled",
    ["method", "path", "status_code", "org_id"],
)

# ── LLM ──────────────────────────────────────────────────────────────────────

LLM_REQUESTS_TOTAL = Counter(
    "cb_llm_requests_total",
    "Total LLM API calls",
    ["provider", "model", "status"],  # status: success | error | circuit_open
)

LLM_LATENCY = Histogram(
    "cb_llm_request_duration_seconds",
    "LLM API call latency in seconds",
    ["provider", "model"],
    buckets=[0.5, 1, 2, 5, 10, 20, 30, 60, 120],
)

LLM_TOKENS_ESTIMATED = Counter(
    "cb_llm_tokens_estimated_total",
    "Estimated tokens sent to LLM (rough: chars/4)",
    ["provider", "org_id"],
)

# ── Embeddings ────────────────────────────────────────────────────────────────

EMBEDDING_LATENCY = Histogram(
    "cb_embedding_duration_seconds",
    "Embedding inference duration in seconds",
    ["model", "batch"],  # batch: "true" | "false"
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5],
)

EMBEDDING_TEXTS_TOTAL = Counter(
    "cb_embedding_texts_total",
    "Total number of texts embedded",
    ["model"],
)

# ── Vector search ─────────────────────────────────────────────────────────────

VECTOR_SEARCH_LATENCY = Histogram(
    "cb_vector_search_duration_seconds",
    "pgvector similarity search duration in seconds",
    ["org_id"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1],
)

VECTOR_SEARCH_TOTAL = Counter(
    "cb_vector_search_total",
    "Total vector similarity searches",
    ["org_id"],
)

# ── Ingestion ─────────────────────────────────────────────────────────────────

INGESTION_RUNS_TOTAL = Counter(
    "cb_ingestion_runs_total",
    "Total ingestion jobs",
    ["source_type", "status", "org_id"],  # status: success | error
)

INGESTION_CHUNKS_TOTAL = Counter(
    "cb_ingestion_chunks_total",
    "Total chunks ingested into the knowledge base",
    ["source_type", "org_id"],
)

INGESTION_LATENCY = Histogram(
    "cb_ingestion_duration_seconds",
    "End-to-end ingestion job duration in seconds",
    ["source_type"],
    buckets=[1, 5, 10, 30, 60, 120, 300],
)

# ── Database ──────────────────────────────────────────────────────────────────

DB_QUERY_LATENCY = Histogram(
    "cb_db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],  # e.g. "select_members", "insert_contribution"
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1],
)

# ── Circuit breakers ──────────────────────────────────────────────────────────

CIRCUIT_BREAKER_STATE = Gauge(
    "cb_circuit_breaker_state",
    "Circuit breaker state: 0=closed (healthy), 1=open (failing)",
    ["service"],
)

CIRCUIT_BREAKER_TRIPS_TOTAL = Counter(
    "cb_circuit_breaker_trips_total",
    "Total times a circuit breaker opened",
    ["service"],
)

# ── HTTP latency histogram (Week 14 — SLO foundation) ────────────────────────
# Paired with cb_http_requests_total. Used for p50 / p95 / p99 latency SLOs.
HTTP_REQUEST_DURATION = Histogram(
    "cb_http_request_duration_seconds",
    "HTTP request duration in seconds (app handler time, excludes GZip)",
    ["method", "path_template", "status_code"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10],
)


# ── Business-outcome metrics (Week 14 — alert on outcomes, not just liveness) ─
SIGNALS_DETECTED_TOTAL = Counter(
    "cb_signals_detected_total",
    "Signals written by the nightly pattern-detection job",
    ["signal_type", "severity", "outcome"],  # outcome: created | updated
)

DIGESTS_SENT_TOTAL = Counter(
    "cb_digests_sent_total",
    "Weekly digest delivery attempts",
    ["delivery_channel", "status"],  # channel: slack|email|in_app, status: sent|failed|skipped
)


# ── Nightly pipeline (Week 16 — RFC #17 follow-up) ───────────────────────────
# Emitted by app/services/nightly_pipeline.py on every run_nightly() call.
# Pairs with cb_digests_sent_total to cover the full "did the night succeed?"
# SLO surface.

NIGHTLY_PIPELINE_RUN_TOTAL = Counter(
    "cb_nightly_pipeline_run_total",
    "Nightly pipeline run outcomes",
    ["status"],  # ok | partial | failed
)

NIGHTLY_STEP_DURATION_SECONDS = Histogram(
    "cb_nightly_step_duration_seconds",
    "Per-step wall-clock duration within the nightly pipeline",
    ["step", "status"],  # step name × ok|failed
    # Buckets chosen for steps that run 50ms to ~10 min.
    buckets=[0.05, 0.25, 1, 5, 15, 60, 180, 600],
)


# ── Application info ──────────────────────────────────────────────────────────

APP_INFO = Info(
    "cb_app",
    "Collective Brain application metadata",
)
