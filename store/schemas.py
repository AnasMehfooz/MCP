"""Pydantic schemas: the contract shared by the REST API and the MCP tools."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Sku = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
]
Price = Annotated[Decimal, Field(gt=0, le=1_000_000, decimal_places=2, description="Price in EUR, e.g. 19.99")]


def to_cents(price: Decimal) -> int:
    return int((price * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_cents(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


class ProductCreate(BaseModel):
    sku: Sku
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    price: Price
    description: str | None = None
    initial_stock: Annotated[int, Field(ge=0)] = 0


class PriceUpdate(BaseModel):
    price: Price


class StockAdjustment(BaseModel):
    delta: int = Field(description="Positive to restock, negative for sales or write-offs")


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku: str
    name: str
    description: str | None
    price: Decimal
    quantity: int
    low_stock: bool


class PriceChange(BaseModel):
    sku: str
    old_price: Decimal
    new_price: Decimal
