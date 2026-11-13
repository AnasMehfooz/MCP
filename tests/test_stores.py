import uuid

import pytest
from pydantic import ValidationError

from store import errors
from store.stores import services
from store.stores.schemas import StoreCreate


def test_create_store_uses_the_blueprint_defaults(session):
    store = services.create_store(session, StoreCreate(slug="demo", name="Demo Store"))
    assert (store.currency, store.locale, store.status) == ("EUR", "de-DE", "draft")
    assert services.get_store(session, store.id) == store
    assert services.get_store_by_slug(session, "demo") == store


def test_duplicate_slug_rejected_and_transaction_stays_usable(session):
    services.create_store(session, StoreCreate(slug="demo", name="Demo Store"))
    with pytest.raises(errors.DuplicateStoreSlug):
        services.create_store(session, StoreCreate(slug="demo", name="Another"))
    services.create_store(session, StoreCreate(slug="demo-2", name="Another"))


@pytest.mark.parametrize("slug", ["Demo", "demo shop", "-demo", "demo-", "de--mo", ""])
def test_slug_must_be_url_safe(slug):
    with pytest.raises(ValidationError):
        StoreCreate(slug=slug, name="x")


def test_unknown_store(session):
    with pytest.raises(errors.StoreNotFound):
        services.get_store(session, uuid.uuid4())
    with pytest.raises(errors.StoreNotFound):
        services.get_store_by_slug(session, "nope")


def test_resolve_uses_the_configured_store(session):
    services.create_store(session, StoreCreate(slug="a", name="A"))
    b = services.create_store(session, StoreCreate(slug="b", name="B"))
    assert services.resolve_store_id(session, b.id) == b.id


def test_resolve_rejects_a_configured_store_that_does_not_exist(session, store_id):
    with pytest.raises(errors.StoreNotFound):
        services.resolve_store_id(session, uuid.uuid4())


def test_resolve_falls_back_to_the_only_store(session, store_id):
    assert services.resolve_store_id(session, None) == store_id


def test_resolve_never_guesses(session):
    with pytest.raises(errors.StoreNotConfigured, match="No store exists yet"):
        services.resolve_store_id(session, None)

    services.create_store(session, StoreCreate(slug="a", name="A"))
    services.create_store(session, StoreCreate(slug="b", name="B"))
    with pytest.raises(errors.StoreNotConfigured, match="Set STORE_ID"):
        services.resolve_store_id(session, None)
