"""MCP Integrator: exposes the store to Claude Desktop over stdio.

Claude Desktop starts this process itself and speaks JSON-RPC over stdin/stdout.
Never print() here: anything on stdout corrupts the protocol. Logs go to stderr.

Run manually for debugging:  python -m store.mcp_server
"""
from __future__ import annotations

import logging
import sys
from decimal import Decimal
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field, ValidationError

from store import services
from store.config import DB_PATH, LOW_STOCK_THRESHOLD
from store.db import init_db, session_scope
from store.schemas import PriceChange, ProductCreate, ProductOut

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("store.mcp")

mcp = MCPServer(
    "ai-store",
    instructions=(
        "You are the store manager for a small e-commerce shop. Prices are in EUR. "
        "Products are identified by SKU (uppercase letters, digits, '-' or '_'). "
        f"Stock at or below {LOW_STOCK_THRESHOLD} units counts as low. "
        "Call list_products before guessing a SKU, and confirm price changes larger than 20% with the user."
    ),
)

PriceArg = Annotated[Decimal, Field(gt=0, le=1_000_000, decimal_places=2, description="Price in EUR, max 2 decimals, e.g. 19.99")]
READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)


def _run(fn, *args, **kwargs):
    """Run a service call in its own transaction and turn domain errors into ToolErrors,
    which Claude sees as a readable tool failure instead of a crash."""
    try:
        with session_scope() as session:
            return fn(session, *args, **kwargs)
    except services.StoreError as exc:
        raise ToolError(str(exc)) from exc


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
    product = _run(services.add_product, data)
    log.info("added %s", product.sku)
    return product


@mcp.tool(annotations=READ_ONLY)
def check_inventory(
    sku: Annotated[str | None, Field(description="Check one product; omit to list all")] = None,
    low_stock_only: Annotated[bool, Field(description="Only return products at or below the low-stock threshold")] = False,
) -> list[ProductOut]:
    """Show stock levels, prices and low-stock flags for one product or the whole catalog."""
    if sku:
        return [_run(services.get_product, sku)]
    return _run(services.list_products, low_stock_only=low_stock_only)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=False, idempotentHint=True, openWorldHint=False))
def update_price(sku: Annotated[str, Field(description="SKU of the product")], new_price: PriceArg) -> PriceChange:
    """Change a product's price. Returns the old and new price."""
    change = _run(services.update_price, sku, new_price)
    log.info("price %s: %s -> %s", change.sku, change.old_price, change.new_price)
    return change


@mcp.tool(annotations=ToolAnnotations(destructiveHint=False, openWorldHint=False))
def adjust_stock(
    sku: Annotated[str, Field(description="SKU of the product")],
    delta: Annotated[int, Field(description="Units to add (restock) or remove (negative, e.g. -2 for a sale)")],
) -> ProductOut:
    """Restock or remove units. Refuses to go below zero."""
    return _run(services.adjust_stock, sku, delta)


def main() -> None:
    init_db()
    log.info("ai-store MCP server starting, database: %s", DB_PATH)
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
