"""Store lifecycle and lookup. Framework-free, like every services module."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from store.db import violated_constraint
from store.errors import DuplicateStoreSlug, StoreNotConfigured, StoreNotFound
from store.stores.models import SLUG_UNIQUE, Store
from store.stores.schemas import StoreCreate, StoreOut


def create_store(session: Session, data: StoreCreate) -> StoreOut:
    store = Store(slug=data.slug, name=data.name, currency=data.currency, locale=data.locale)
    try:
        with session.begin_nested():  # savepoint: a rejected insert leaves the caller's transaction usable
            session.add(store)
    except IntegrityError as exc:
        if violated_constraint(exc) == SLUG_UNIQUE:
            raise DuplicateStoreSlug(data.slug) from exc
        raise
    return StoreOut.model_validate(store)


def get_store(session: Session, store_id: UUID) -> StoreOut:
    store = session.get(Store, store_id)
    if store is None:
        raise StoreNotFound(store_id)
    return StoreOut.model_validate(store)


def get_store_by_slug(session: Session, slug: str) -> StoreOut:
    store = session.scalar(select(Store).where(Store.slug == slug))
    if store is None:
        raise StoreNotFound(slug)
    return StoreOut.model_validate(store)


def resolve_store_id(session: Session, configured: UUID | None) -> UUID:
    """The store a single-store process works on: STORE_ID if set, otherwise the only store.

    Used by the MCP server and, until owner login exists, by the REST API. It never guesses
    between several stores.
    """
    if configured is not None:
        return get_store(session, configured).id

    ids = session.scalars(select(Store.id).limit(2)).all()
    if len(ids) == 1:
        return ids[0]
    if not ids:
        raise StoreNotConfigured("No store exists yet. Create the demo store with `python -m scripts.seed`.")
    raise StoreNotConfigured("Several stores exist. Set STORE_ID to the id of the store to manage.")
