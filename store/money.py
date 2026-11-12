"""Money helpers. Prices are stored as integer cents, so 0.10 + 0.20 is exactly 0.30."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def to_cents(price: Decimal) -> int:
    return int((price * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_cents(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))
