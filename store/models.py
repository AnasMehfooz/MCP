"""Database Modeler: two tables, one-to-one.

Prices are stored as integer cents to avoid float rounding.
Inventory is split from Product so stock changes never touch catalog rows.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from store.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("price_cents > 0", name="ck_price_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    price_cents: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    inventory: Mapped[Inventory] = relationship(
        back_populates="product", cascade="all, delete-orphan", lazy="joined"
    )


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (CheckConstraint("quantity >= 0", name="ck_quantity_non_negative"),)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    product: Mapped[Product] = relationship(back_populates="inventory")
