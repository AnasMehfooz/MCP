from decimal import Decimal

import pytest
from pydantic import ValidationError

from store import services
from store.schemas import ProductCreate


def _add(session, sku="TEE-1", price="19.99", stock=10):
    return services.add_product(session, ProductCreate(sku=sku, name="Tee", price=Decimal(price), initial_stock=stock))


def test_add_and_get_product(session):
    out = _add(session, sku=" tee-1 ")
    assert out.sku == "TEE-1"  # normalized
    assert out.price == Decimal("19.99")
    assert services.get_product(session, "tee-1").quantity == 10


def test_duplicate_sku_rejected(session):
    _add(session)
    with pytest.raises(services.DuplicateSku):
        _add(session)


def test_price_stored_without_float_error(session):
    _add(session, price="0.10")
    change = services.update_price(session, "TEE-1", Decimal("0.30"))
    assert (change.old_price, change.new_price) == (Decimal("0.10"), Decimal("0.30"))


def test_unknown_sku(session):
    with pytest.raises(services.ProductNotFound):
        services.update_price(session, "NOPE", Decimal("1"))


def test_stock_cannot_go_negative(session):
    _add(session, stock=2)
    assert services.adjust_stock(session, "TEE-1", -2).quantity == 0
    with pytest.raises(services.InsufficientStock):
        services.adjust_stock(session, "TEE-1", -1)


def test_low_stock_filter(session):
    _add(session, sku="A", stock=50)
    _add(session, sku="B", stock=1)
    assert [p.sku for p in services.list_products(session, low_stock_only=True)] == ["B"]


@pytest.mark.parametrize("bad", [{"price": Decimal("0")}, {"price": Decimal("1.999")}, {"sku": "bad sku"}, {"initial_stock": -1}])
def test_schema_validation(bad):
    data = {"sku": "OK-1", "name": "x", "price": Decimal("1.00")} | bad
    with pytest.raises(ValidationError):
        ProductCreate(**data)
