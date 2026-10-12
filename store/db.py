"""Engine and session handling. The API and the MCP server are separate processes
sharing one SQLite file, so WAL mode and a busy timeout are enabled."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from store.config import DATABASE_URL, DB_PATH


class Base(DeclarativeBase):
    pass


def make_engine(url: str = DATABASE_URL) -> Engine:
    if url == DATABASE_URL:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 15})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record) -> None:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")  # API and MCP server can read/write concurrently
        cur.close()

    return engine


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db(bind: Engine = engine) -> None:
    from store import models  # noqa: F401  (register tables on Base.metadata)

    Base.metadata.create_all(bind)


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
