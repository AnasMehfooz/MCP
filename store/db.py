"""Engine, declarative Base and session handling for Postgres 16 with pgvector.

Tables are created and changed by Alembic (`alembic upgrade head`), never at startup.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import DateTime, Engine, MetaData, Text, Uuid, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from store.config import settings

# Every constraint gets a predictable name, so migrations can alter or drop it and services
# can tell which one an IntegrityError violated.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Column types for plain annotations: Mapped[str] is text, Mapped[datetime] is timestamptz.
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        str: Text,
        datetime: DateTime(timezone=True),
        UUID: Uuid,
        dict[str, Any]: JSONB,
    }


def make_engine(url: str | None = None) -> Engine:
    # pool_pre_ping: the MCP server lives as long as Claude Desktop does, and the database
    # container may restart underneath it.
    return create_engine(url or settings.database_url, pool_pre_ping=True)


engine = make_engine()
DATABASE_LABEL = engine.url.render_as_string(hide_password=True)  # safe to log
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session] = SessionLocal) -> Iterator[Session]:
    """One unit of work: commit on success, roll back on any error."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def violated_constraint(exc: IntegrityError) -> str | None:
    """Name of the constraint behind an IntegrityError, from the driver's diagnostics."""
    return getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
