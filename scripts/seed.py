"""Create the database and add a few demo products. Safe to run twice.

Run from the project root:  python -m scripts.seed
"""
from decimal import Decimal

from store import services
from store.config import DB_PATH
from store.db import init_db, session_scope
from store.schemas import ProductCreate

DEMO = [
    ProductCreate(sku="TSHIRT-BLK-M", name="Black T-Shirt (M)", price=Decimal("19.99"), initial_stock=40),
    ProductCreate(sku="HOODIE-GRY-L", name="Grey Hoodie (L)", price=Decimal("49.90"), initial_stock=3),
    ProductCreate(sku="MUG-LOGO", name="Logo Coffee Mug", price=Decimal("12.50"), initial_stock=0),
]


def main() -> None:
    init_db()
    for item in DEMO:
        try:
            with session_scope() as session:
                services.add_product(session, item)
            print(f"added   {item.sku}")
        except services.DuplicateSku:
            print(f"exists  {item.sku}")
    print(f"database: {DB_PATH}")


if __name__ == "__main__":
    main()
