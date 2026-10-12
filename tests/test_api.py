import pytest
from fastapi.testclient import TestClient

from store.api import app, get_session
from store.db import session_scope


@pytest.fixture
def client(session_factory, monkeypatch):
    monkeypatch.setattr("store.api.init_db", lambda: None)

    def _session():
        with session_scope(session_factory) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_crud_flow(client):
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
