"""Test database setup.

Default: every test gets a fresh in-memory SQLite database, no services needed.

With TEST_DATABASE_URL set, the same tests run on Postgres instead:

    docker compose up -d postgres
    TEST_DATABASE_URL=postgresql+psycopg://store:store@localhost:5432/store_test pytest

Each test then gets its own throwaway schema (created before, dropped after), so tests
stay isolated, leave nothing behind, and work with code that commits or runs in a
subprocess (the MCP end-to-end test).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from store.catalog import models  # noqa: F401  (register tables on Base.metadata)
from store.db import Base, session_scope

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


def pytest_report_header() -> str:
    if not TEST_DATABASE_URL:
        return "database: SQLite (in-memory); set TEST_DATABASE_URL to run on Postgres"
    return f"database: {make_url(TEST_DATABASE_URL).render_as_string(hide_password=True)}"


@pytest.fixture
def pg_url() -> Iterator[str | None]:
    """URL of an isolated Postgres schema for this test, or None when running on SQLite."""
    if not TEST_DATABASE_URL:
        yield None
        return

    schema = f"test_{uuid.uuid4().hex}"
    admin = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        # public stays on the path so extension types such as pgvector's `vector` resolve.
        url = make_url(TEST_DATABASE_URL).update_query_dict({"options": f"-csearch_path={schema},public"})
        yield url.render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def session_factory(pg_url: str | None) -> Iterator[sessionmaker[Session]]:
    if pg_url:
        engine = create_engine(pg_url)
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_scope(session_factory) as s:
        yield s
