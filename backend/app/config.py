import os
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM Provider
    llm_provider: Literal["claude", "ollama", "mistral"] = "ollama"
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    mistral_api_key: str = ""
    mistral_model: str = "Qwen/Qwen2.5-72B-Instruct"

    @property
    def effective_mistral_api_key(self) -> str:
        """Return mistral_api_key, falling back to HF_TOKEN (auto-set on HF Spaces)."""
        if self.mistral_api_key:
            return self.mistral_api_key
        return os.environ.get("HF_TOKEN", "")

    # Agent mode
    agent_mode: Literal["langgraph", "rag"] = "rag"
    agent_max_iterations: int = 10

    # JWT Auth — no default; must be set via CB_JWT_SECRET env var.
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    # Google OAuth
    google_client_id: str = ""

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # ── Supabase ─────────────────────────────────────────────────────────
    # Transaction-mode pooler URL (port 6543) — used at runtime by the app
    database_url: str = ""

    # Direct session URL (port 5432) — used ONLY by Alembic migrations
    # Never used by the running FastAPI app (pooler handles that).
    migration_database_url: str = ""

    # Supabase project credentials (used by supabase-py client for auth helpers)
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    # Connection pool settings (PostgreSQL)
    db_pool_size: int = 25
    db_max_overflow: int = 50
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800  # 30 minutes

    # Redis — optional, falls back to in-memory when not available
    redis_url: str = ""

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 64

    # RAG
    retrieval_top_k: int = 8
    context_max_tokens: int = 3000

    # Rate limiting
    rate_limit_requests: int = 60
    rate_limit_ai_requests: int = 10

    # Slack Bot Integration
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_signing_secret: str = ""

    # GitHub Webhook Integration
    github_webhook_secret: str = ""

    # ── Phase 5: External integrations ───────────────────────────────────
    # Notion
    notion_token: str = ""

    # Google Docs / Drive (service account JSON file path OR OAuth access token)
    google_service_account_file: str = ""
    google_access_token: str = ""

    # Confluence
    confluence_url: str = ""  # e.g. https://yoursite.atlassian.net/wiki
    confluence_user: str = ""  # email for Confluence Cloud
    confluence_token: str = ""  # API token
    confluence_cloud: bool = True

    # Knowledge verification
    knowledge_staleness_threshold_days: int = 30

    # Decision Intelligence
    decision_extraction_enabled: bool = True
    decision_extraction_min_confidence: float = 0.6
    risk_radar_scan_interval_hours: int = 24

    # Notifications
    notification_webhook_timeout: int = 10
    notification_retry_count: int = 3

    # Logging
    log_level: str = "INFO"

    @property
    def effective_database_url(self) -> str:
        """Runtime DB URL — must be set via CB_DATABASE_URL.

        Whitespace is stripped to defend against env vars copy-pasted with
        trailing spaces/newlines — we hit a production incident where a
        trailing-space in the DB name caused psycopg2 to report
        ``database "postgres  " does not exist``.
        """
        if not self.database_url:
            raise RuntimeError(
                "CB_DATABASE_URL is not set. Copy .env.example to backend/.env and fill in your Supabase pooler URL."
            )
        return self.database_url.strip()

    @property
    def effective_migration_url(self) -> str:
        """Direct URL for Alembic migrations — falls back to database_url if unset.

        Same strip() defense as above. Alembic needs a session-mode (port
        5432) connection, not the transaction pooler (port 6543), because
        prepared statements + advisory locks don't survive pgbouncer in
        transaction mode.
        """
        raw = self.migration_database_url or self.database_url
        return (raw or "").strip()

    @property
    def is_postgres(self) -> bool:
        return self.database_url.strip().startswith("postgresql")

    model_config = {"env_file": ".env", "env_prefix": "CB_", "extra": "ignore"}


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
