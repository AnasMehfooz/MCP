import threading
import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from store import errors
from store.catalog import services
from store.catalog.models import Product
from store.catalog.schemas import ProductCreate
from store.db import session_scope


def _add(session, store_id, sku="TEE-1", price="19.99", stock=10, name="Tee"):
    data = ProductCreate(sku=sku, name=name, price=Decimal(price), initial_stock=stock)
    return services.add_product(session, store_id, data)


def test_add_and_get_product(session, store_id):
    out = _add(session, store_id, sku=" tee-1 ")
    assert out.sku == "TEE-1"  # normalized
    assert out.price == Decimal("19.99")
    assert services.get_product(session, store_id, "tee-1").quantity == 10


def test_duplicate_sku_rejected(session, store_id):
    _add(session, store_id)
    with pytest.raises(errors.DuplicateSku):
        _add(session, store_id)


def test_rejected_insert_keeps_the_transaction_usable(session, store_id):
    """The importer adds many products in one transaction and must survive a bad row."""
    _add(session, store_id, sku="A")
    with pytest.raises(errors.DuplicateSku):
        _add(session, store_id, sku="A")
    _add(session, store_id, sku="B")
    session.commit()
    assert [p.sku for p in services.list_products(session, store_id)] == ["A", "B"]


def test_price_stored_without_float_error(session, store_id):
    _add(session, store_id, price="0.10")
    change = services.update_price(session, store_id, "TEE-1", Decimal("0.30"))
    assert (change.old_price, change.new_price) == (Decimal("0.10"), Decimal("0.30"))


def test_unknown_sku(session, store_id):
    with pytest.raises(errors.ProductNotFound):
        services.update_price(session, store_id, "NOPE", Decimal("1"))


def test_unknown_store(session):
    with pytest.raises(errors.StoreNotFound):
        _add(session, uuid.uuid4())


def test_stock_cannot_go_negative(session, store_id):
    _add(session, store_id, stock=2)
    assert services.adjust_stock(session, store_id, "TEE-1", -2).quantity == 0
    with pytest.raises(errors.InsufficientStock):
        services.adjust_stock(session, store_id, "TEE-1", -1)


def test_concurrent_sales_cannot_oversell(session_factory, store_id):
    """Two buyers want 3 of the last 5. The second must wait for the first and then be refused;
    without the row lock both would read 5 and both would succeed."""
    with session_scope(session_factory) as s:
        _add(s, store_id, stock=5)

    second: dict[str, object] = {}

    def second_buyer() -> None:
        try:
            with session_scope(session_factory) as s:
                second["result"] = services.adjust_stock(s, store_id, "TEE-1", -3)
        except Exception as exc:
            second["error"] = exc

    with session_scope(session_factory) as first:
        assert services.adjust_stock(first, store_id, "TEE-1", -3).quantity == 2  # not committed yet
        thread = threading.Thread(target=second_buyer)
        thread.start()
        thread.join(timeout=0.5)
        assert thread.is_alive(), "the second sale should be waiting for the first one's lock"
    thread.join(timeout=10)

    assert isinstance(second.get("error"), errors.InsufficientStock), second
    with session_scope(session_factory) as s:
        assert services.get_product(s, store_id, "TEE-1").quantity == 2


def test_low_stock_filter(session, store_id):
    _add(session, store_id, sku="A", stock=50)
    _add(session, store_id, sku="B", stock=1)
    assert [p.sku for p in services.list_products(session, store_id, low_stock_only=True)] == ["B"]


def test_handles_come_from_the_name_and_stay_unique(session, store_id):
    _add(session, store_id, sku="A", name="Bio T-Shirt (Größe M)")
    _add(session, store_id, sku="B", name="Tee")
    _add(session, store_id, sku="C", name="Tee")
    _add(session, store_id, sku="D", name="Tee")
    handles = session.scalars(select(Product.handle).order_by(Product.id)).all()
    assert handles == ["bio-t-shirt-groesse-m", "tee", "tee-2", "tee-3"]


def test_handle_taken_by_a_concurrent_insert_is_retried(session, store_id, monkeypatch):
    _add(session, store_id, sku="A", name="Tee")
    real = services._free_handle
    answers = iter(["tee"])  # stale answer, as if another transaction had just inserted "tee"
    monkeypatch.setattr(services, "_free_handle", lambda *args: next(answers, None) or real(*args))

    _add(session, store_id, sku="B", name="Tee")

    assert session.scalars(select(Product.handle).order_by(Product.id)).all() == ["tee", "tee-2"]


@pytest.mark.parametrize(
    "bad", [{"price": Decimal("0")}, {"price": Decimal("1.999")}, {"sku": "bad sku"}, {"initial_stock": -1}]
)
def test_schema_validation(bad):
    data = {"sku": "OK-1", "name": "x", "price": Decimal("1.00")} | bad
    with pytest.raises(ValidationError):
        ProductCreate(**data)
