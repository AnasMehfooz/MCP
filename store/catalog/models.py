"""Catalog tables: products, their variants, stock, images and collections.

A product is what the shopper sees (title, copy, images); a variant is what they buy
(one SKU with a price). Prices are integer cents to avoid float rounding, and stock sits in
its own table so stock writes never lock catalog rows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from store.db import Base

EMBEDDING_DIMENSIONS = 1024  # bge-m3

# Named here because services map violations of these to domain errors.
HANDLE_UNIQUE = "uq_products_store_id_handle"
SKU_UNIQUE = "uq_variants_store_id_sku"
PRODUCT_STORE_FK = "fk_products_store_id_stores"


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("store_id", "handle", name=HANDLE_UNIQUE),
        CheckConstraint("status IN ('draft', 'active', 'archived')", name="status"),
        Index(
            "ix_products_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    store_id: Mapped[UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    handle: Mapped[str]  # URL slug, unique per store
    title: Mapped[str]
    description: Mapped[str | None]  # published copy only; drafts live elsewhere until approved
    # material, size, care, ...: what the copy validator checks claims against
    attributes: Mapped[dict[str, Any]] = mapped_column(server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(server_default="draft")
    seo_title: Mapped[str | None]
    seo_description: Mapped[str | None]
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    variants: Mapped[list[Variant]] = relationship(
        back_populates="product", cascade="all, delete-orphan", passive_deletes=True, order_by="Variant.id"
    )


class Variant(Base):
    __tablename__ = "variants"
    __table_args__ = (
        UniqueConstraint("store_id", "sku", name=SKU_UNIQUE),
        CheckConstraint("price_cents > 0", name="price_positive"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    # Repeated from the product so the SKU can be unique per store.
    store_id: Mapped[UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"))
    sku: Mapped[str]
    options: Mapped[dict[str, Any]] = mapped_column(server_default=text("'{}'::jsonb"))  # {"size": "M"}
    price_cents: Mapped[int] = mapped_column(Integer)

    product: Mapped[Product] = relationship(back_populates="variants")
    inventory: Mapped[Inventory] = relationship(
        back_populates="variant", cascade="all, delete-orphan", passive_deletes=True
    )


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (CheckConstraint("quantity >= 0", name="quantity_non_negative"),)

    variant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("variants.id", ondelete="CASCADE"), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    variant: Mapped[Variant] = relationship(back_populates="inventory")


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"))
    url: Mapped[str]
    alt_text: Mapped[str | None]
    position: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))


class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = (UniqueConstraint("store_id", "handle"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    store_id: Mapped[UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    handle: Mapped[str]
    title: Mapped[str]
    description: Mapped[str | None]


class CollectionProduct(Base):
    __tablename__ = "collection_products"

    collection_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
