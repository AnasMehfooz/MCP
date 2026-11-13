from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from store.api.app import app
from store.api.deps import get_session
from store.catalog import services as catalog
from store.config import settings
from store.db import session_scope
from store.stores import services as stores
from store.stores.schemas import StoreCreate


@pytest.fixture
def client(session_factory):
    def _session():
        with session_scope(session_factory) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_crud_flow(client, store_id):
    r = client.post("/products", json={"sku": "mug-1", "name": "Mug", "price": "12.50", "initial_stock": 4})
    assert r.status_code == 201
    assert r.json()["sku"] == "MUG-1" and r.json()["low_stock"] is True

    assert client.post("/products", json={"sku": "MUG-1", "name": "Mug", "price": "1"}).status_code == 409

    r = client.patch("/products/MUG-1/price", json={"price": "14.00"})
    assert r.json() == {"sku": "MUG-1", "old_price": "12.50", "new_price": "14.00"}

    assert client.post("/products/MUG-1/stock", json={"delta": 10}).json()["quantity"] == 14
    assert client.post("/products/MUG-1/stock", json={"delta": -99}).status_code == 409
    assert client.get("/products/NOPE").status_code == 404
    assert len(client.get("/products").json()) == 1


def test_no_store_yet_is_a_clear_503(client):
    r = client.get("/products")
    assert r.status_code == 503
    assert "No store exists yet" in r.json()["detail"]


def test_store_id_selects_the_store_and_is_required_once_there_are_two(client, session_factory, store_id, monkeypatch):
    with session_scope(session_factory) as s:
        other = stores.create_store(s, StoreCreate(slug="other-shop", name="Other Shop")).id

    assert client.get("/products").status_code == 503  # two stores, none chosen: never guess

    monkeypatch.setattr(settings, "store_id", other)
    assert client.post("/products", json={"sku": "A", "name": "A", "price": "1.00"}).status_code == 201

    with session_scope(session_factory) as s:
        assert catalog.get_product(s, other, "A").price == Decimal("1.00")
        assert catalog.list_products(s, store_id) == []
