"""MCP Integrator: exposes the store to Claude Desktop over stdio.

Claude Desktop starts this process itself and speaks JSON-RPC over stdin/stdout.
Never print() here: anything on stdout corrupts the protocol. Logs go to stderr.

Run manually for debugging:  python -m store.mcp_server
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field, ValidationError
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from store.catalog import services as catalog
from store.catalog.schemas import PriceChange, ProductCreate, ProductOut
from store.config import settings
from store.context import ToolContext
from store.db import DATABASE_LABEL, session_scope
from store.errors import StoreError
from store.stores import services as stores

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("store.mcp")

mcp = MCPServer(
    "ai-store",
    instructions=(
        "You are the store manager for a small e-commerce shop. Prices are in EUR. "
        "Products are identified by SKU (uppercase letters, digits, '-' or '_'). "
        f"Stock at or below {settings.low_stock_threshold} units counts as low. "
        "Call check_inventory before guessing a SKU, and confirm price changes larger than 20% with the user."
    ),
)

PriceArg = Annotated[
    Decimal, Field(gt=0, le=1_000_000, decimal_places=2, description="Price in EUR, max 2 decimals, e.g. 19.99")
]
READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)

_UNDEFINED_TABLE = "42P01"  # Postgres SQLSTATE


def _context(session: Session) -> ToolContext:
    """Claude Desktop is the owner's own client for one store. Both facts come from this
    process (STORE_ID, or the only store in the database), never from a tool's arguments."""
    return ToolContext(store_id=stores.resolve_store_id(session, settings.store_id), actor="owner")


@contextmanager
def _call() -> Iterator[tuple[Session, ToolContext]]:
    """One tool call: its own transaction, plus the context saying who calls and for which store.

    Domain errors and a database that is down or not migrated become ToolErrors, which Claude
    sees as a readable tool failure it can relay or correct, instead of a crash.
    """
    try:
        with session_scope() as session:
            yield session, _context(session)
    except StoreError as exc:
        raise ToolError(str(exc)) from exc
    except OperationalError as exc:
        reason = str(exc.orig).strip().splitlines()[0]
        log.error("database error: %s", reason)
        raise ToolError(
            f"Cannot use the store database at {DATABASE_LABEL}: {reason}. "
            "If Postgres is not running, start it with `docker compose up -d postgres`."
        ) from exc
    except ProgrammingError as exc:
        if getattr(exc.orig, "sqlstate", None) != _UNDEFINED_TABLE:
            raise
        log.error("database not migrated: %s", exc.orig)
        raise ToolError("The store database has no tables yet. Run `alembic upgrade head` and try again.") from exc


@mcp.tool(annotations=ToolAnnotations(destructiveHint=False, openWorldHint=False))
def add_product(
    sku: Annotated[str, Field(description="Unique stock-keeping unit, e.g. TSHIRT-BLK-M")],
    name: Annotated[str, Field(min_length=1, max_length=200)],
    price: PriceArg,
    initial_stock: Annotated[int, Field(ge=0, description="Units on hand")] = 0,
    description: str | None = None,
) -> ProductOut:
    """Add a new product to the catalog with its starting stock level."""
    try:
        data = ProductCreate(sku=sku, name=name, price=price, initial_stock=initial_stock, description=description)
    except ValidationError as exc:
        raise ToolError("; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())) from exc
    with _call() as (session, ctx):
        product = catalog.add_product(session, ctx.store_id, data)
    log.info("added %s", product.sku)
    return product


@mcp.tool(annotations=READ_ONLY)
def check_inventory(
    sku: Annotated[str | None, Field(description="Check one product; omit to list all")] = None,
    low_stock_only: Annotated[
        bool, Field(description="Only return products at or below the low-stock threshold")
    ] = False,
) -> list[ProductOut]:
    """Show stock levels, prices and low-stock flags for one product or the whole catalog."""
    with _call() as (session, ctx):
        if sku:
            return [catalog.get_product(session, ctx.store_id, sku)]
        return catalog.list_products(session, ctx.store_id, low_stock_only=low_stock_only)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=False, idempotentHint=True, openWorldHint=False))
def update_price(sku: Annotated[str, Field(description="SKU of the product")], new_price: PriceArg) -> PriceChange:
    """Change a product's price. Returns the old and new price."""
    with _call() as (session, ctx):
        change = catalog.update_price(session, ctx.store_id, sku, new_price)
    log.info("price %s: %s -> %s", change.sku, change.old_price, change.new_price)
    return change


@mcp.tool(annotations=ToolAnnotations(destructiveHint=False, openWorldHint=False))
def adjust_stock(
    sku: Annotated[str, Field(description="SKU of the product")],
    delta: Annotated[int, Field(description="Units to add (restock) or remove (negative, e.g. -2 for a sale)")],
) -> ProductOut:
    """Restock or remove units. Refuses to go below zero."""
    with _call() as (session, ctx):
        return catalog.adjust_stock(session, ctx.store_id, sku, delta)


def main() -> None:
    log.info("ai-store MCP server starting, database: %s", DATABASE_LABEL)
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
