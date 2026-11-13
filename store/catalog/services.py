"""Catalog business logic. Framework-free: FastAPI routes and MCP tools are thin adapters over
these functions, so both front doors enforce exactly the same rules.

Every function takes the store it works on, and every query starts from `_variants`, so
no caller can read or change another store's catalog.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from store.catalog.models import HANDLE_UNIQUE, PRODUCT_STORE_FK, SKU_UNIQUE, Inventory, Product, Variant
from store.catalog.schemas import PriceChange, ProductCreate, ProductOut
from store.config import settings
from store.db import violated_constraint
from store.errors import DuplicateSku, InsufficientStock, ProductNotFound, StoreError, StoreNotFound
from store.money import from_cents, to_cents
from store.slugs import slugify

_HANDLE_ATTEMPTS = 3


def _variants(store_id: UUID) -> Select[tuple[Variant]]:
    """Variants of one store, with product and stock loaded. The only entry point for reads."""
    return (
        select(Variant)
        .where(Variant.store_id == store_id)
        .options(joinedload(Variant.product), joinedload(Variant.inventory))
    )


def _get(session: Session, store_id: UUID, sku: str) -> Variant:
    variant = session.scalar(_variants(store_id).where(Variant.sku == sku.strip().upper()))
    if variant is None:
        raise ProductNotFound(sku)
    return variant


def _to_out(variant: Variant) -> ProductOut:
    quantity = variant.inventory.quantity if variant.inventory else 0
    return ProductOut(
        sku=variant.sku,
        name=variant.product.title,
        description=variant.product.description,
        price=from_cents(variant.price_cents),
        quantity=quantity,
        low_stock=quantity <= settings.low_stock_threshold,
    )


def _free_handle(session: Session, store_id: UUID, title: str) -> str:
    """URL handle for a new product: the slugified title, then -2, -3, ... while it is taken."""
    base = slugify(title, fallback="product")
    taken = set(
        session.scalars(
            select(Product.handle).where(
                Product.store_id == store_id,
                or_(Product.handle == base, Product.handle.startswith(f"{base}-", autoescape=True)),
            )
        )
    )
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def add_product(session: Session, store_id: UUID, data: ProductCreate) -> ProductOut:
    """Create a product with a single variant (the SKU) and its stock row."""
    for _ in range(_HANDLE_ATTEMPTS):
        variant = Variant(
            store_id=store_id,
            sku=data.sku,
            price_cents=to_cents(data.price),
            inventory=Inventory(quantity=data.initial_stock),
        )
        product = Product(
            store_id=store_id,
            handle=_free_handle(session, store_id, data.name),
            title=data.name,
            description=data.description,
            variants=[variant],
        )
        try:
            # Savepoint: a rejected insert rolls back only itself, so a caller adding many
            # products in one transaction (the importer) can carry on with the next row.
            with session.begin_nested():
                session.add(product)
        except IntegrityError as exc:
            constraint = violated_constraint(exc)
            if constraint == SKU_UNIQUE:
                raise DuplicateSku(data.sku) from exc
            if constraint == PRODUCT_STORE_FK:
                raise StoreNotFound(store_id) from exc
            if constraint != HANDLE_UNIQUE:
                raise
            # Another transaction took the handle between the lookup and the insert: look again.
        else:
            return _to_out(variant)
    raise StoreError(f"Could not reserve a URL handle for '{data.name}'. Please try again.")


def list_products(session: Session, store_id: UUID, *, low_stock_only: bool = False) -> list[ProductOut]:
    items = [_to_out(v) for v in session.scalars(_variants(store_id).order_by(Variant.sku))]
    return [i for i in items if i.low_stock] if low_stock_only else items


def get_product(session: Session, store_id: UUID, sku: str) -> ProductOut:
    return _to_out(_get(session, store_id, sku))


def update_price(session: Session, store_id: UUID, sku: str, new_price: Decimal) -> PriceChange:
    variant = _get(session, store_id, sku)
    old = from_cents(variant.price_cents)
    variant.price_cents = to_cents(new_price)
    session.flush()
    return PriceChange(sku=variant.sku, old_price=old, new_price=from_cents(variant.price_cents))


def adjust_stock(session: Session, store_id: UUID, sku: str, delta: int) -> ProductOut:
    variant = _get(session, store_id, sku)
    # Lock the stock row and re-read it: without this, two concurrent sales could both check
    # the same quantity and oversell. populate_existing refreshes the copy `_get` just loaded.
    inventory = session.scalars(
        select(Inventory)
        .where(Inventory.variant_id == variant.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()
    if inventory.quantity + delta < 0:
        raise InsufficientStock(variant.sku, inventory.quantity, -delta)
    inventory.quantity += delta
    session.flush()
    return _to_out(variant)
