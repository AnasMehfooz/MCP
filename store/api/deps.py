"""Dependencies shared by every router."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from store.config import settings
from store.db import session_scope
from store.errors import StoreError
from store.stores import services as stores


def get_session() -> Iterator[Session]:
    with session_scope() as session:
        yield session


def get_store_id(session: Session = Depends(get_session)) -> UUID:
    """The store a request works on.

    Until owner login exists, the API serves one store, chosen like the MCP server's:
    STORE_ID, or the only store in the database. With auth, this dependency will read the
    store from the owner's session instead, and the routes stay as they are.
    """
    try:
        return stores.resolve_store_id(session, settings.store_id)
    except StoreError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
