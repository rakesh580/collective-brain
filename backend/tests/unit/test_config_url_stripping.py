"""Regression test for DB URL whitespace handling.

Production incident: ``CB_MIGRATION_DATABASE_URL`` was set with trailing
whitespace in the DB name portion, causing psycopg2 to report
``database "postgres  " does not exist``. ``effective_database_url`` and
``effective_migration_url`` now call ``.strip()`` so leading/trailing
whitespace from copy-paste errors is defused at the boundary.
"""

from __future__ import annotations


def _mk_settings(db_url: str | None, migration_url: str | None = None):
    from app.config import Settings

    kwargs = {}
    if db_url is not None:
        kwargs["database_url"] = db_url
    if migration_url is not None:
        kwargs["migration_database_url"] = migration_url
    return Settings(**kwargs)


def test_effective_database_url_strips_trailing_whitespace():
    s = _mk_settings(db_url="postgresql://u:p@h:5432/postgres  ")
    assert s.effective_database_url == "postgresql://u:p@h:5432/postgres"


def test_effective_database_url_strips_leading_whitespace():
    s = _mk_settings(db_url="  postgresql://u:p@h:5432/postgres")
    assert s.effective_database_url == "postgresql://u:p@h:5432/postgres"


def test_effective_database_url_strips_newlines():
    s = _mk_settings(db_url="postgresql://u:p@h:5432/postgres\n")
    assert s.effective_database_url == "postgresql://u:p@h:5432/postgres"


def test_effective_migration_url_strips_whitespace():
    s = _mk_settings(
        db_url="postgresql://u:p@h:6543/postgres",
        migration_url="postgresql://u:p@h:5432/postgres  \n",
    )
    assert s.effective_migration_url == "postgresql://u:p@h:5432/postgres"


def test_effective_migration_url_falls_back_to_database_url():
    """When migration_database_url is unset, fall back to the main URL (also stripped)."""
    s = _mk_settings(db_url="  postgresql://u:p@h:5432/postgres\t", migration_url="")
    assert s.effective_migration_url == "postgresql://u:p@h:5432/postgres"
