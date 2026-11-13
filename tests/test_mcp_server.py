"""The MCP tools called in-process: where their ToolContext comes from, and how setup
problems reach Claude. The real stdio round trip is in test_mcp_e2e.py."""

import dataclasses
import uuid
from decimal import Decimal

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from store import mcp_server
from store.catalog import services as catalog
from store.config import settings
from store.context import ToolContext
from store.db import session_scope
from store.stores import services as stores
from store.stores.schemas import StoreCreate


def _use(monkeypatch, factory) -> None:
    """Point the MCP server at this test's database."""
    monkeypatch.setattr(mcp_server, "session_scope", lambda: session_scope(factory))


@pytest.fixture
def tools(session_factory, monkeypatch):
    _use(monkeypatch, session_factory)
    return mcp_server


def test_tools_act_as_the_owner_of_the_only_store(tools, session_factory, store_id):
    with session_scope(session_factory) as s:
        assert mcp_server._context(s) == ToolContext(store_id=store_id, actor="owner")

    tools.add_product(sku="tee-1", name="Tee", price=Decimal("19.99"), initial_stock=3)
    assert [p.sku for p in tools.check_inventory(low_stock_only=True)] == ["TEE-1"]
    assert tools.update_price("TEE-1", Decimal("24.99")).old_price == Decimal("19.99")
    assert tools.adjust_stock("TEE-1", -3).quantity == 0


def test_store_id_decides_which_store_the_tools_touch(tools, session_factory, store_id, monkeypatch):
    with session_scope(session_factory) as s:
        other = stores.create_store(s, StoreCreate(slug="other-shop", name="Other Shop")).id

    with pytest.raises(ToolError, match="Set STORE_ID"):  # two stores, none chosen: never guess
        tools.check_inventory()

    monkeypatch.setattr(settings, "store_id", other)
    tools.add_product(sku="A", name="A", price=Decimal("1.00"))

    with session_scope(session_factory) as s:
        assert [p.sku for p in catalog.list_products(s, other)] == ["A"]
        assert catalog.list_products(s, store_id) == []


def test_context_is_immutable():
    ctx = ToolContext(store_id=uuid.uuid4(), actor="owner")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.store_id = uuid.uuid4()


def test_domain_errors_become_tool_errors(tools, store_id):
    with pytest.raises(ToolError, match="No product with SKU 'NOPE'"):
        tools.update_price("NOPE", Decimal("1.00"))


def test_no_store_yet_tells_how_to_create_one(tools):
    with pytest.raises(ToolError, match=r"python -m scripts\.seed"):
        tools.check_inventory()


def test_database_without_tables_tells_how_to_migrate(engine, monkeypatch):
    _use(monkeypatch, sessionmaker(bind=engine))  # empty schema: migrations never ran
    with pytest.raises(ToolError, match="alembic upgrade head"):
        mcp_server.check_inventory()


def test_unreachable_database_tells_how_to_start_it(monkeypatch):
    nowhere = create_engine("postgresql+psycopg://store:store@127.0.0.1:1/store")  # nothing listens on port 1
    _use(monkeypatch, sessionmaker(bind=nowhere))
    with pytest.raises(ToolError, match="docker compose up -d postgres"):
        mcp_server.check_inventory()
