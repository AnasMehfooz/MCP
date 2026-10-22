# Headless AI Store

[![tests](https://github.com/AnasMehfooz/MCP/actions/workflows/tests.yml/badge.svg)](https://github.com/AnasMehfooz/MCP/actions/workflows/tests.yml)

A local e-commerce backend where **Claude Desktop is the frontend**. Claude manages the catalog through MCP tools; the same logic is also exposed as a REST API.

```text
Claude Desktop ──stdio/JSON-RPC──► server.py ─► store/mcp_server.py ─┐
                                                                      ├─► store/services.py ─► SQLite (data/store.db, WAL)
Browser / scripts ──HTTP──► uvicorn store.api:app ───────────────────┘
```

The MCP server calls the service layer **in-process** rather than calling FastAPI over HTTP. Claude Desktop spawns it on demand, so there is no second server to keep running, and both front doors enforce the same rules.

## Structure

```text
ai-store/
├── server.py              Claude Desktop entry point (fixes sys.path for any cwd)
├── requirements.txt
├── pyproject.toml         pytest config
├── store/
│   ├── config.py          Absolute DB path, low-stock threshold (env-overridable)
│   ├── db.py              Engine, WAL + foreign keys, session_scope()
│   ├── models.py          Database Modeler: Product, Inventory
│   ├── schemas.py         Pydantic contracts, EUR <-> cents conversion
│   ├── services.py        Business logic + domain errors (framework-free)
│   ├── api.py             FastAPI Engineer: REST adapter
│   └── mcp_server.py      MCP Integrator: tools for Claude
├── scripts/seed.py        Demo data
├── tests/                 services, API, and a real MCP stdio session
└── data/store.db          Created on first run
```

## Data model

| Table | Columns | Rules |
| --- | --- | --- |
| `products` | `id`, `sku` (unique, uppercase), `name`, `description`, `price_cents`, `created_at`, `updated_at` | `price_cents > 0` |
| `inventory` | `product_id` (PK, FK → products, cascade), `quantity`, `updated_at` | `quantity >= 0` |

Prices are integer cents, so 0.10 + 0.20 is exactly 0.30. Inventory sits in its own table so stock writes never lock catalog rows.

## MCP tools

| Tool | Purpose | Annotations |
| --- | --- | --- |
| `add_product(sku, name, price, initial_stock=0, description=None)` | Create product + stock row | not destructive |
| `check_inventory(sku=None, low_stock_only=False)` | One product or the whole catalog, with low-stock flags | read-only |
| `update_price(sku, new_price)` | Returns old and new price | idempotent |
| `adjust_stock(sku, delta)` | Restock or sell; refuses negative stock | not destructive |

Domain errors (unknown SKU, duplicate SKU, insufficient stock, invalid input) are raised as `ToolError`, so Claude gets a readable message and can correct itself instead of the call crashing. Tools return Pydantic models, so Claude also receives structured output.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate             # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.seed             # optional demo products
pytest                             # 12 tests, incl. an end-to-end MCP session
```

Requires **MCP Python SDK 2.x** (`MCPServer`). v1's `FastMCP` import does not exist in 2.x.

## Connect Claude Desktop

Open *Settings → Developer → Edit Config*, or edit the file directly:

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

Use **absolute paths** and the venv's Python, so the right dependencies are found:

```json
{
  "mcpServers": {
    "ai-store": {
      "command": "C:\\Users\\<you>\\code\\ai-store\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\<you>\\code\\ai-store\\server.py"]
    }
  }
}
```

macOS/Linux: `"command": "/path/to/ai-store/.venv/bin/python"`, `"args": ["/path/to/ai-store/server.py"]`.

Fully quit and restart Claude Desktop (from the tray / menu bar, not just the window). The `ai-store` tools then appear in the tools menu. Try:

> Add a "Canvas Tote Bag" for €15, SKU TOTE-NAT, with 25 in stock. Then show me everything that's low on stock and raise the hoodie price by 10%.

**Troubleshooting:** server logs go to stderr, which Claude Desktop writes to `%APPDATA%\Claude\logs\mcp-server-ai-store.log` (macOS: `~/Library/Logs/Claude/`). Never `print()` in the MCP server, because stdout carries the protocol. To inspect tools interactively: `mcp dev server.py`.

## REST API (optional)

```bash
uvicorn store.api:app --reload      # docs at http://127.0.0.1:8000/docs
```

| Method | Path | |
| --- | --- | --- |
| POST | `/products` | 201, 409 on duplicate SKU |
| GET | `/products?low_stock_only=` | list |
| GET | `/products/{sku}` | 404 if unknown |
| PATCH | `/products/{sku}/price` | `{"price": "24.99"}` |
| POST | `/products/{sku}/stock` | `{"delta": -2}`, 409 if insufficient |

API and MCP server can run at the same time against the same database (WAL mode, 15 s busy timeout).

## Configuration

| Env var | Default |
| --- | --- |
| `STORE_DB_PATH` | `<project>/data/store.db` |
| `STORE_LOW_STOCK_THRESHOLD` | `5` |

Set them in Claude Desktop via an `"env": {...}` block next to `"args"`.

## Next steps

- Orders table and a `create_order` tool that decrements stock in one transaction
- Alembic migrations once the schema changes
- MCP resources (e.g. `store://catalog`) so Claude can read the catalog without a tool call
- Human confirmation for large price changes via MCP elicitation

## License

MIT, see [LICENSE](LICENSE).

Built with AI pair programming (Claude).
