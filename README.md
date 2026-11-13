# Headless AI Store

A local e-commerce backend where **Claude Desktop is the frontend**. Claude manages the catalog through MCP tools; the same logic is also exposed as a REST API.

```text
Claude Desktop ──stdio/JSON-RPC──► server.py ─► store/mcp_server.py ─────┐
                                                                          ├─► store/<domain>/services.py ─► Postgres 16 + pgvector
Browser / scripts / Stripe ──HTTP──► uvicorn store.api.app:app ──────────┘
```

The MCP server calls the service layer **in-process** rather than calling FastAPI over HTTP. Claude Desktop spawns it on demand, so there is no second server to keep running, and both front doors enforce the same rules.

This is the foundation of v2, the AI store builder planned in [docs/BLUEPRINT.md](docs/BLUEPRINT.md): Postgres instead of SQLite, a `store_id` on every table, and Alembic migrations. Decisions are recorded in [docs/decisions/](docs/decisions/).

## Structure

```text
ai-store/
├── server.py                 Claude Desktop entry point for source checkouts
├── pyproject.toml            Package metadata, `ai-store` command, ruff, pytest, import-linter contracts
├── requirements.txt
├── docker-compose.yml        Postgres 16 + pgvector, Phoenix tracing
├── alembic.ini, migrations/  Schema migrations (Alembic)
├── store/
│   ├── config.py             Settings from the environment or .env (pydantic-settings)
│   ├── db.py                 Engine, Base, session_scope()
│   ├── metadata.py           Imports every domain's models, for Alembic and the tests
│   ├── context.py            ToolContext: who calls a tool, and for which store
│   ├── errors.py             StoreError hierarchy (messages are safe to show to users and Claude)
│   ├── money.py              EUR <-> cents conversion
│   ├── slugs.py              URL slugs for product handles
│   ├── stores/               The store (tenant): models, schemas, services
│   ├── catalog/              Products, variants, inventory, images, collections
│   ├── api/                  FastAPI Engineer: app.py, deps.py, routes/ (products, webhooks)
│   └── mcp_server.py         MCP Integrator: tools for Claude
├── scripts/                  seed.py (demo store), sample_products.csv (importer fixture)
├── skills/store-manager/     Agent skill (SKILL.md) that teaches Claude the store workflows
├── docs/                     BLUEPRINT.md (the v2 plan), decisions/ (one ADR per choice)
└── tests/                    services, tenancy, migrations, API, webhooks, and a real MCP stdio session
```

Each domain package has `models.py`, `schemas.py` and `services.py`. Adapters (`api/`, `mcp_server.py`) import services, never models, and services never import adapters; `lint-imports` enforces this.

## Data model

| Table | Holds | Rules |
| --- | --- | --- |
| `stores` | One row per store: `slug`, `name`, `currency`, `locale`, `status` | `slug` unique |
| `products` | What the shopper sees: `handle`, `title`, `description`, `attributes` (jsonb), SEO fields, `embedding` (`vector(1024)`, HNSW index) | `(store_id, handle)` unique |
| `variants` | What the shopper buys: `sku`, `options` (jsonb), `price_cents` | `(store_id, sku)` unique, `price_cents > 0` |
| `inventory` | `variant_id` (PK, FK → variants, cascade), `quantity` | `quantity >= 0` |
| `product_images` | `url`, `alt_text`, `position` per product | |
| `collections`, `collection_products` | Groups of products and their order | `(store_id, handle)` unique |

Every row belongs to a store, directly through `store_id` or through its parent row, and every service function takes the store it works on. Prices are integer cents, so 0.10 + 0.20 is exactly 0.30. Inventory sits in its own table so stock writes never lock catalog rows; `adjust_stock` locks the one stock row it changes, so two concurrent sales cannot oversell.

## MCP tools

| Tool | Purpose | Annotations |
| --- | --- | --- |
| `add_product(sku, name, price, initial_stock=0, description=None)` | Create a product with one variant and its stock row | not destructive |
| `check_inventory(sku=None, low_stock_only=False)` | One product or the whole catalog, with low-stock flags | read-only |
| `update_price(sku, new_price)` | Returns old and new price | idempotent |
| `adjust_stock(sku, delta)` | Restock or sell; refuses negative stock | not destructive |

Every call runs with a `ToolContext` that the server builds itself: the store comes from `STORE_ID` (or is the only store in the database) and the actor is the owner. Neither can be set through a tool's arguments.

Domain errors (unknown SKU, duplicate SKU, insufficient stock, invalid input) are raised as `ToolError`, so Claude gets a readable message and can correct itself instead of the call crashing. The same goes for setup problems: if Postgres is stopped, the tables are missing or no store exists yet, the tool answers with what to run. Tools return Pydantic models, so Claude also receives structured output.

## Setup

Requires Python 3.11+ and Docker.

```bash
python -m venv .venv
.venv\Scripts\activate                 # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
docker compose up -d --wait postgres   # Postgres 16 + pgvector on localhost:5432
alembic upgrade head                   # create the tables
python -m scripts.seed                 # demo store with 3 products; prints its STORE_ID
pytest                                 # 70 tests, incl. an end-to-end MCP session
```

The first start of the database creates `store` (development) and `store_test` (pytest), both with the `vector` extension. `docker compose up -d` without a service name also starts [Arize Phoenix](https://arize.com/docs/phoenix) (trace UI on http://localhost:6006); nothing sends traces yet. Copy `.env.example` to `.env` to change credentials, ports or any setting below.

v1's zero-setup `uvx` install relied on SQLite and no longer applies: v2 needs Postgres and its migrations, so it runs from a source checkout. Data in an old `store.db` is not carried over.

Requires **MCP Python SDK 2.x** (`MCPServer`). v1's `FastMCP` import does not exist in 2.x.

### Tests

The suite runs on Postgres, like the app. Each test gets its own throwaway schema in `store_test`, so tests are isolated and leave nothing behind. Point `TEST_DATABASE_URL` (environment or `.env`) at another database if needed.

### Migrations

```bash
alembic revision --autogenerate -m "orders" --rev-id 0002   # new migration from model changes
alembic upgrade head                                        # apply
alembic check                                               # fail if models and migrations differ
alembic upgrade head --sql                                  # print the SQL instead of running it
```

Change the models first, autogenerate, then read the generated file before applying it. A model in a new domain package must be imported in `store/metadata.py`. `tests/test_migrations.py` runs the real migrations and fails when they and the models disagree.

### Lint, format and architecture checks

```bash
pre-commit install                 # once; then every commit runs the three checks below
ruff check . && ruff format .      # lint (config in pyproject.toml) and format, 120 columns
lint-imports                       # import-linter contracts: adapters -> services -> models, never back
```

### Sample product sheet

`scripts/sample_products.csv` is the importer's test fixture: 30 products (57 variant rows), 10 of them with a planted problem such as a missing price, a duplicate SKU or conflicting variants. `scripts/sample_products.problems.json` lists each problem with its file lines and the expected handling.

## Connect Claude Desktop from a source checkout

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

The server reads `.env` from the checkout, so it finds the database without further settings. With more than one store in the database, tell it which one to manage: `"env": {"STORE_ID": "<id printed by scripts.seed>"}` next to `"args"`.

Fully quit and restart Claude Desktop (from the tray / menu bar, not just the window). The `ai-store` tools then appear in the tools menu. Try:

> Add a "Canvas Tote Bag" for €15, SKU TOTE-NAT, with 25 in stock. Then show me everything that's low on stock and raise the hoodie price by 10%.

**Troubleshooting:** Postgres must be running (`docker compose up -d --wait postgres`); if it is not, the tools say so, and they work again once it is up, without a restart of Claude Desktop. Server logs go to stderr, which Claude Desktop writes to `%APPDATA%\Claude\logs\mcp-server-ai-store.log` (macOS: `~/Library/Logs/Claude/`). Never `print()` in the MCP server, because stdout carries the protocol. To inspect tools interactively: `mcp dev server.py`.

## REST API (optional)

```bash
uvicorn store.api.app:app --reload      # docs at http://127.0.0.1:8000/docs
```

| Method | Path | |
| --- | --- | --- |
| POST | `/products` | 201, 409 on duplicate SKU |
| GET | `/products?low_stock_only=` | list |
| GET | `/products/{sku}` | 404 if unknown |
| PATCH | `/products/{sku}/price` | `{"price": "24.99"}` |
| POST | `/products/{sku}/stock` | `{"delta": -2}`, 409 if insufficient |
| POST | `/webhooks/stripe` | 200 for an event signed by Stripe, 400 otherwise |

The product routes have no login yet: they serve the same single store as the MCP server (`STORE_ID`, or the only store), so keep the API on localhost. API and MCP server can run at the same time against the same database.

### Stripe webhook (test mode)

`POST /webhooks/stripe` verifies the `Stripe-Signature` header and acknowledges the event. It does not act on events yet; that arrives with the orders tables. To try it with the [Stripe CLI](https://docs.stripe.com/stripe-cli):

```bash
stripe login
stripe listen --forward-to localhost:8000/webhooks/stripe   # prints the signing secret: whsec_...
# put it in .env:  STRIPE_WEBHOOK_SECRET=whsec_...  then start (or restart) uvicorn
stripe trigger checkout.session.completed                   # the listener shows [200] for each event
```

Without `STRIPE_WEBHOOK_SECRET` the route answers 503 to everything, and a request with a missing, wrong or old signature gets 400.

## Configuration

| Variable | Default | |
| --- | --- | --- |
| `STORE_DATABASE_URL` | `postgresql+psycopg://store:store@localhost:5432/store` | The docker-compose database |
| `STORE_ID` | unset | Store the MCP server and the REST API work on. Unset: the only store in the database |
| `STORE_LOW_STOCK_THRESHOLD` | `5` | |
| `STRIPE_WEBHOOK_SECRET` | unset | Signing secret for `/webhooks/stripe` |
| `TEST_DATABASE_URL` | `postgresql+psycopg://store:store@localhost:5432/store_test` | pytest only |

Set them in `.env` in the project root, in the shell, or in Claude Desktop via an `"env": {...}` block next to `"args"`. Real environment variables win over `.env`.

## Agent skill

`skills/store-manager/SKILL.md` tells the agent when and how to use the tools: bulk CSV import with validation, inventory audits, recording sales, and price changes with confirmation above 20%. Copy the `store-manager` folder into `~/.claude/skills/` (Claude Code) or upload it as a skill in Claude Desktop.

## Next steps

The full plan is in [docs/BLUEPRINT.md](docs/BLUEPRINT.md). Next up:

- Orders tables, Stripe Checkout, and a webhook that marks the order paid and decrements stock in one transaction
- Product import from CSV, tested against `scripts/sample_products.csv`
- MCP resources (e.g. `store://catalog`) so Claude can read the catalog without a tool call
- Human confirmation for large price changes via MCP elicitation
