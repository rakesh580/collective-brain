from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # LLM Provider
    llm_provider: Literal["claude", "ollama", "mistral"] = "ollama"
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    mistral_api_key: str = ""
    mistral_model: str = "Qwen/Qwen2.5-72B-Instruct"

    # Agent mode
    agent_mode: Literal["langgraph", "rag"] = "rag"
    agent_max_iterations: int = 10

    # JWT Auth
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # ChromaDB
    chroma_persist_dir: str = "./data/chroma_db"

    # Database — supports both PostgreSQL and SQLite
    # PostgreSQL: postgresql://user:pass@host:5432/dbname
    # SQLite:     sqlite:///./data/collective_brain.db
    database_url: str = "sqlite:///./data/collective_brain.db"

    # Keep legacy sqlite_url as alias for backward compat
    sqlite_url: str = "sqlite:///./data/collective_brain.db"

    # Connection pool settings (PostgreSQL only, ignored for SQLite)
    db_pool_size: int = 10
    db_max_overflow: int = 20
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
    rate_limit_requests: int = 60  # per minute
    rate_limit_ai_requests: int = 10  # AI queries per minute per user

    @property
    def effective_database_url(self) -> str:
        """Return database_url if set, else sqlite_url for backward compat."""
        if self.database_url != "sqlite:///./data/collective_brain.db":
            return self.database_url
        return self.sqlite_url

    @property
    def is_postgres(self) -> bool:
        return self.effective_database_url.startswith("postgresql")

    model_config = {"env_file": ".env", "env_prefix": "CB_"}


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
