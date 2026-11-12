"""Dependencies shared by every router."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from store.db import session_scope


def get_session() -> Iterator[Session]:
    with session_scope() as session:
        yield session
