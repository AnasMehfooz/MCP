"""Business logic. Framework-free: FastAPI routes and MCP tools are thin adapters over these
functions, so both front doors enforce exactly the same rules."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from store.config import LOW_STOCK_THRESHOLD
from store.models import Inventory, Product
from store.schemas import PriceChange, ProductCreate, ProductOut, from_cents, to_cents


class StoreError(Exception):
    """Base for domain errors; the message is safe to show to users and to Claude."""


class ProductNotFound(StoreError):
    def __init__(self, sku: str) -> None:
        super().__init__(f"No product with SKU '{sku}'.")


class DuplicateSku(StoreError):
    def __init__(self, sku: str) -> None:
        super().__init__(f"A product with SKU '{sku}' already exists.")


class InsufficientStock(StoreError):
    def __init__(self, sku: str, available: int, requested: int) -> None:
        super().__init__(f"Cannot remove {requested} of '{sku}': only {available} in stock.")


def _to_out(p: Product) -> ProductOut:
    qty = p.inventory.quantity if p.inventory else 0
    return ProductOut(
        sku=p.sku,
        name=p.name,
        description=p.description,
        price=from_cents(p.price_cents),
        quantity=qty,
        low_stock=qty <= LOW_STOCK_THRESHOLD,
    )


def _get(session: Session, sku: str) -> Product:
    product = session.scalar(select(Product).where(Product.sku == sku.strip().upper()))
    if product is None:
        raise ProductNotFound(sku)
    return product


def add_product(session: Session, data: ProductCreate) -> ProductOut:
    product = Product(
        sku=data.sku,
        name=data.name,
        description=data.description,
        price_cents=to_cents(data.price),
        inventory=Inventory(quantity=data.initial_stock),
    )
    session.add(product)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise DuplicateSku(data.sku) from exc
    return _to_out(product)


def list_products(session: Session, *, low_stock_only: bool = False) -> list[ProductOut]:
    products = session.scalars(select(Product).order_by(Product.sku)).unique().all()
    items = [_to_out(p) for p in products]
    return [i for i in items if i.low_stock] if low_stock_only else items


def get_product(session: Session, sku: str) -> ProductOut:
    return _to_out(_get(session, sku))


def update_price(session: Session, sku: str, new_price: Decimal) -> PriceChange:
    product = _get(session, sku)
    old = from_cents(product.price_cents)
    product.price_cents = to_cents(new_price)
    session.flush()
    return PriceChange(sku=product.sku, old_price=old, new_price=from_cents(product.price_cents))


def adjust_stock(session: Session, sku: str, delta: int) -> ProductOut:
    product = _get(session, sku)
    current = product.inventory.quantity
    if current + delta < 0:
        raise InsufficientStock(product.sku, current, -delta)
    product.inventory.quantity = current + delta
    session.flush()
    return _to_out(product)
