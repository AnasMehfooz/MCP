"""Test database setup. The suite runs on Postgres, like the app:

    docker compose up -d postgres
    pytest

TEST_DATABASE_URL (environment or .env) selects the database; the default is the
`store_test` database that docker-compose creates. Each test gets its own throwaway schema
(created before, dropped after), so tests are isolated, leave nothing behind, and work with
code that commits or runs in another process (the MCP end-to-end test).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from uuid import UUID

import pytest
from dotenv import dotenv_values
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from store.config import PROJECT_ROOT, settings
from store.db import session_scope
from store.metadata import metadata
from store.stores import services as stores
from store.stores.schemas import StoreCreate

TEST_DATABASE_URL = (
    os.getenv("TEST_DATABASE_URL")
    or dotenv_values(PROJECT_ROOT / ".env").get("TEST_DATABASE_URL")
    or "postgresql+psycopg://store:store@localhost:5432/store_test"
)
_LABEL = make_url(TEST_DATABASE_URL).render_as_string(hide_password=True)


def pytest_report_header() -> str:
    return f"database: {_LABEL}"


@pytest.fixture(autouse=True)
def _pinned_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never depend on what the developer has in .env."""
    monkeypatch.setattr(settings, "store_id", None)
    monkeypatch.setattr(settings, "low_stock_threshold", 5)
    monkeypatch.setattr(settings, "stripe_webhook_secret", None)


@pytest.fixture(scope="session")
def postgres() -> Iterator[Engine]:
    """Autocommit engine on the test database, used to create and drop the per-test schemas."""
    admin = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            # In `public`, so every test schema can use the type and no test can drop it.
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public"))
    except OperationalError as exc:
        reason = str(exc.orig).strip().splitlines()[0]
        pytest.fail(
            f"Postgres is not reachable at {_LABEL}: {reason}\nStart it with `docker compose up -d postgres`.",
            pytrace=False,
        )
    yield admin
    admin.dispose()


@pytest.fixture
def db_url(postgres: Engine) -> Iterator[str]:
    """URL of an empty schema that exists for this test only."""
    schema = f"test_{uuid.uuid4().hex}"
    with postgres.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        # public stays on the path so the `vector` type resolves.
        url = make_url(TEST_DATABASE_URL).update_query_dict({"options": f"-csearch_path={schema},public"})
        yield url.render_as_string(hide_password=False)
    finally:
        with postgres.connect() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.fixture
def engine(db_url: str) -> Iterator[Engine]:
    """Engine on the empty schema: no tables yet."""
    engine = create_engine(db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    """All tables created from the models. tests/test_migrations.py proves that this is the
    same schema the migrations build."""
    metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_scope(session_factory) as s:
        yield s


@pytest.fixture
def store_id(session_factory: sessionmaker[Session]) -> UUID:
    """A committed store, so other sessions and processes can see it."""
    with session_scope(session_factory) as s:
        return stores.create_store(s, StoreCreate(slug="test-shop", name="Test Shop")).id
