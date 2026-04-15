"""Alembic environment configuration.

Uses CB_MIGRATION_DATABASE_URL (direct port-5432 session connection) for
migrations, falling back to CB_DATABASE_URL.  Never uses the transaction
pooler (port 6543) — Alembic requires a persistent session connection.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add backend dir to path so app modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.database import Base  # noqa: E402
import app.models  # noqa: E402, F401 — register all models with Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Use the direct (session-mode) URL for migrations
db_url = (
    os.environ.get("CB_MIGRATION_DATABASE_URL")
    or os.environ.get("CB_DATABASE_URL")
)
if not db_url:
    raise RuntimeError(
        "Set CB_MIGRATION_DATABASE_URL (port 5432 direct URL) before running migrations."
    )
config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # single connection for migrations
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
