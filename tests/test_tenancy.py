"""Two stores in one database never see or change each other's catalog."""

from decimal import Decimal

import pytest

from store import errors
from store.catalog import services
from store.catalog.schemas import ProductCreate
from store.stores import services as stores
from store.stores.schemas import StoreCreate


@pytest.fixture
def other_store_id(session):
    return stores.create_store(session, StoreCreate(slug="other-shop", name="Other Shop")).id


def _add(session, store_id, sku, price="10.00", stock=10):
    data = ProductCreate(sku=sku, name=f"Product {sku}", price=Decimal(price), initial_stock=stock)
    return services.add_product(session, store_id, data)


def test_same_sku_can_exist_in_two_stores(session, store_id, other_store_id):
    _add(session, store_id, "TEE-1", price="10.00")
    _add(session, other_store_id, "TEE-1", price="99.00")

    assert services.get_product(session, store_id, "TEE-1").price == Decimal("10.00")
    assert services.get_product(session, other_store_id, "TEE-1").price == Decimal("99.00")


def test_listing_shows_only_the_own_store(session, store_id, other_store_id):
    _add(session, store_id, "MINE")
    _add(session, other_store_id, "THEIRS", stock=1)

    assert [p.sku for p in services.list_products(session, store_id)] == ["MINE"]
    assert [p.sku for p in services.list_products(session, other_store_id, low_stock_only=True)] == ["THEIRS"]


def test_another_stores_product_cannot_be_read_or_changed(session, store_id, other_store_id):
    _add(session, other_store_id, "THEIRS")

    with pytest.raises(errors.ProductNotFound):
        services.get_product(session, store_id, "THEIRS")
    with pytest.raises(errors.ProductNotFound):
        services.update_price(session, store_id, "THEIRS", Decimal("0.01"))
    with pytest.raises(errors.ProductNotFound):
        services.adjust_stock(session, store_id, "THEIRS", -10)

    untouched = services.get_product(session, other_store_id, "THEIRS")
    assert (untouched.price, untouched.quantity) == (Decimal("10.00"), 10)
