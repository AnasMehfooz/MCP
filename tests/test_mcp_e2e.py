"""End-to-end: launches the MCP server as a subprocess over stdio, exactly like Claude Desktop,
and calls its tools through the official MCP client."""

import os
import re
import sys

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from sqlalchemy import text

from store.config import PROJECT_ROOT


async def _session_calls(env: dict[str, str]) -> dict:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "store.mcp_server"],
        cwd=str(PROJECT_ROOT),
        env={**os.environ, **env},
    )
    results = {}
    async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
        init = await client.initialize()
        results["instructions"] = init.instructions
        results["tools"] = sorted(t.name for t in (await client.list_tools()).tools)
        results["add"] = await client.call_tool(
            "add_product", {"sku": "tshirt-blk-m", "name": "Black T-Shirt (M)", "price": 19.99, "initial_stock": 3}
        )
        results["dup"] = await client.call_tool("add_product", {"sku": "TSHIRT-BLK-M", "name": "x", "price": 1})
        results["price"] = await client.call_tool("update_price", {"sku": "TSHIRT-BLK-M", "new_price": "24.99"})
        results["inv"] = await client.call_tool("check_inventory", {"low_stock_only": True})
        results["bad_price"] = await client.call_tool("update_price", {"sku": "TSHIRT-BLK-M", "new_price": -5})
    return results


def test_claude_desktop_style_session(db_url, engine, session_factory, store_id):
    # The server gets its database and its store from the environment, as in claude_desktop_config.json.
    env = {"STORE_DATABASE_URL": db_url, "STORE_ID": str(store_id), "STORE_LOW_STOCK_THRESHOLD": "5"}
    r = anyio.run(_session_calls, env)

    assert r["tools"] == ["add_product", "adjust_stock", "check_inventory", "update_price"]

    # Instructions must only point Claude at tools that exist.
    referenced = set(re.findall(r"\b[a-z]+_[a-z_]+\b", r["instructions"]))
    assert referenced <= set(r["tools"]), referenced - set(r["tools"])
    assert "check_inventory" in referenced

    assert not r["add"].is_error
    assert r["add"].structured_content["sku"] == "TSHIRT-BLK-M"

    assert r["dup"].is_error
    assert "already exists" in r["dup"].content[0].text

    assert r["price"].structured_content == {"sku": "TSHIRT-BLK-M", "old_price": "19.99", "new_price": "24.99"}

    inv = r["inv"].structured_content["result"]
    assert inv[0]["quantity"] == 3 and inv[0]["low_stock"] is True

    assert r["bad_price"].is_error

    # The tool calls really hit Postgres, in the store the environment named.
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT p.store_id, p.handle, v.sku, v.price_cents, i.quantity "
                "FROM products p JOIN variants v ON v.product_id = p.id JOIN inventory i ON i.variant_id = v.id"
            )
        ).all()
    assert rows == [(store_id, "black-t-shirt-m", "TSHIRT-BLK-M", 2499, 3)]
