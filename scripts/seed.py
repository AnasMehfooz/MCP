"""Create the demo store and a few demo products. Safe to run twice.

Run from the project root, after `alembic upgrade head`:  python -m scripts.seed
"""

from decimal import Decimal

from store.catalog import services as catalog
from store.catalog.schemas import ProductCreate
from store.db import DATABASE_LABEL, session_scope
from store.errors import DuplicateSku, DuplicateStoreSlug
from store.stores import services as stores
from store.stores.schemas import StoreCreate

DEMO_STORE = StoreCreate(slug="demo", name="Demo Store")
DEMO_PRODUCTS = [
    ProductCreate(sku="TSHIRT-BLK-M", name="Black T-Shirt (M)", price=Decimal("19.99"), initial_stock=40),
    ProductCreate(sku="HOODIE-GRY-L", name="Grey Hoodie (L)", price=Decimal("49.90"), initial_stock=3),
    ProductCreate(sku="MUG-LOGO", name="Logo Coffee Mug", price=Decimal("12.50"), initial_stock=0),
]


def main() -> None:
    with session_scope() as session:
        try:
            store = stores.create_store(session, DEMO_STORE)
            print(f"created store '{store.slug}'")
        except DuplicateStoreSlug:
            store = stores.get_store_by_slug(session, DEMO_STORE.slug)
            print(f"store '{store.slug}' exists")

        for item in DEMO_PRODUCTS:
            try:
                catalog.add_product(session, store.id, item)
                print(f"added   {item.sku}")
            except DuplicateSku:
                print(f"exists  {item.sku}")

    print(f"database: {DATABASE_LABEL}")
    print(f"STORE_ID={store.id}")


if __name__ == "__main__":
    main()
