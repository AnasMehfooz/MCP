"""Alembic environment: where migrations get their database and their table definitions.

The URL comes from the app settings (STORE_DATABASE_URL or .env) and the tables from
store.metadata, which imports every domain's models.
"""

from __future__ import annotations

from logging.config import fileConfig
from typing import Any

import pgvector.sqlalchemy
from alembic import context
from sqlalchemy import Connection, create_engine, pool

from store.config import settings
from store.metadata import metadata

config = context.config

# Tests pass in a connection to a throwaway schema; everything else is the command line.
injected_connection: Connection | None = config.attributes.get("connection")

if injected_connection is None and config.config_file_name is not None:
    fileConfig(config.config_file_name)


def render_item(type_: str, obj: Any, autogen_context: Any) -> str | bool:
    """Autogenerate hook: write pgvector columns as `pgvector.sqlalchemy.Vector(n)` and add
    the import, so a generated revision runs as written."""
    if type_ == "type" and isinstance(obj, pgvector.sqlalchemy.Vector):
        autogen_context.imports.add("import pgvector.sqlalchemy")
        return f"pgvector.sqlalchemy.Vector({obj.dim})"
    return False  # default rendering


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL without connecting."""
    context.configure(
        url=settings.database_url,
        target_metadata=metadata,
        render_item=render_item,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=metadata, render_item=render_item)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if injected_connection is not None:
        _run(injected_connection)
        return
    engine = create_engine(settings.database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        _run(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
