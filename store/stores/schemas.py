"""Pydantic schemas for stores."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

Slug = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=63, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$"),
]


class StoreCreate(BaseModel):
    slug: Slug
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] = "EUR"  # ISO 4217
    locale: Annotated[str, StringConstraints(pattern=r"^[a-z]{2}-[A-Z]{2}$")] = "de-DE"


class StoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    currency: str
    locale: str
    status: str
