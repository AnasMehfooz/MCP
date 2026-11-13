"""Tenancy: one row per store. Every other table points back here through store_id."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CHAR, CheckConstraint, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from store.db import Base

SLUG_UNIQUE = "uq_stores_slug"


class Store(Base):
    __tablename__ = "stores"
    __table_args__ = (
        UniqueConstraint("slug", name=SLUG_UNIQUE),
        CheckConstraint("status IN ('draft', 'live')", name="status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    slug: Mapped[str]  # /s/{slug}/ in storefront URLs
    name: Mapped[str]
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="EUR")
    locale: Mapped[str] = mapped_column(server_default="de-DE")
    status: Mapped[str] = mapped_column(server_default="draft")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
