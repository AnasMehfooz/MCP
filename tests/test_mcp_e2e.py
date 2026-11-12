"""End-to-end: launches the MCP server as a subprocess over stdio, exactly like Claude Desktop,
and calls its tools through the official MCP client."""

import os
import re
import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent


async def _session_calls(db_env: dict[str, str]) -> dict:
    # Drop any inherited URL so a SQLite run can never reach a real database.
    base_env = {k: v for k, v in os.environ.items() if k != "STORE_DATABASE_URL"}
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "store.mcp_server"],
        cwd=str(ROOT),
        env={**base_env, **db_env},
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


def test_claude_desktop_style_session(tmp_path, pg_url):
    db_env = {"STORE_DATABASE_URL": pg_url} if pg_url else {"STORE_DB_PATH": str(tmp_path / "store.db")}
    r = anyio.run(_session_calls, db_env)

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

    # The tool calls really hit the database the server was pointed at.
    if pg_url:
        engine = create_engine(pg_url)
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM products")) == 1
        engine.dispose()
    else:
        assert (tmp_path / "store.db").exists()
