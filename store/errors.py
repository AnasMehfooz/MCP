"""Domain errors shared by every package.

The message of a StoreError is safe to show to users and to Claude: the REST API maps these
to HTTP status codes and the MCP server to ToolError.
"""

from __future__ import annotations


class StoreError(Exception):
    """Base for domain errors; the message is safe to show to users and to Claude."""


# --- catalog


class ProductNotFound(StoreError):
    def __init__(self, sku: str) -> None:
        super().__init__(f"No product with SKU '{sku}'.")


class DuplicateSku(StoreError):
    def __init__(self, sku: str) -> None:
        super().__init__(f"A product with SKU '{sku}' already exists.")


class InsufficientStock(StoreError):
    def __init__(self, sku: str, available: int, requested: int) -> None:
        super().__init__(f"Cannot remove {requested} of '{sku}': only {available} in stock.")


# --- stores


class StoreNotFound(StoreError):
    def __init__(self, ref: object) -> None:
        super().__init__(f"No store '{ref}'.")


class DuplicateStoreSlug(StoreError):
    def __init__(self, slug: str) -> None:
        super().__init__(f"A store with slug '{slug}' already exists.")


class StoreNotConfigured(StoreError):
    """STORE_ID is unset and the database does not hold exactly one store to fall back on."""
