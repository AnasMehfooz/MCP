---
name: store-manager
description: Run a small e-commerce catalog through the ai-store MCP server - add products, bulk-import from CSV, audit and restock low inventory, record sales, and apply price changes safely. Use when the user wants to manage products, stock levels or prices in their ai-store database.
---

# Store Manager

Operate the `ai-store` MCP server as the store's back office. The server holds the catalog (products, EUR prices, stock) in SQLite; you are the interface.

## Requirements

The `ai-store` MCP server must be connected. Check that these tools exist before starting:

| Tool | Use it for |
| --- | --- |
| `check_inventory(sku?, low_stock_only?)` | Reading one product or the full catalog. Read-only. |
| `add_product(sku, name, price, initial_stock?, description?)` | Creating a product with its starting stock. |
| `update_price(sku, new_price)` | Changing a price. Returns old and new price. |
| `adjust_stock(sku, delta)` | Restocking (positive) or recording sales/write-offs (negative). |

If the tools are missing, stop and tell the user to install the server. With [uv](https://docs.astral.sh/uv/) installed, Claude Code users run:

```bash
claude mcp add ai-store -- uvx --from git+https://github.com/AnasMehfooz/mcp ai-store
```

Claude Desktop users add `"ai-store": {"command": "uvx", "args": ["--from", "git+https://github.com/AnasMehfooz/mcp", "ai-store"]}` under `mcpServers` in `claude_desktop_config.json` and restart. Full instructions: https://github.com/AnasMehfooz/mcp. Do not simulate store data.

## Ground rules

1. **Never guess a SKU.** Call `check_inventory()` first and match on the product name. If two products match, ask.
2. **SKU format:** uppercase letters, digits, `-` and `_`, max 64 chars. Build new SKUs as `CATEGORY-VARIANT-SIZE` (e.g. `HOODIE-GRY-L`). The server uppercases input, so do not treat case differences as different SKUs.
3. **Prices are EUR with at most 2 decimals.** When computing percentage changes, round half-up to cents and show the exact result before applying.
4. **Confirm before large or bulk changes:** any price change above 20%, any change touching more than 5 products, and any stock write-off (negative delta that is not a sale).
5. **Read errors and recover.** Tool errors are plain messages (unknown SKU, duplicate SKU, insufficient stock, invalid input). Fix the input or ask the user; never retry the same call unchanged.
6. **Report what changed,** not what you attempted: use the values the tools return.

## Workflows

### Add a product

1. `check_inventory()` to confirm the SKU and name are not taken.
2. If the user gave no SKU, propose one following rule 2 and use it unless they object.
3. `add_product(...)`. Write a one-sentence `description` if the user gave enough detail; otherwise leave it empty rather than inventing features.
4. Reply with SKU, name, price and stock from the returned product.

### Bulk import from CSV or a pasted list

1. Parse the rows into `sku, name, price, initial_stock, description`. Expected headers are flexible (`Product`, `Title`, `Qty`, `Stock`, `Preis`...); map them and state the mapping.
2. Validate every row before writing anything: missing name or price, price <= 0, more than 2 decimals, negative stock, malformed SKU, duplicates within the file.
3. `check_inventory()` once and flag rows whose SKU already exists.
4. Show a summary: `N new, N already exist, N invalid (with reasons)`. Ask whether existing SKUs should be skipped or updated (price via `update_price`, stock via `adjust_stock` to reach the file's quantity).
5. Write the approved rows one tool call at a time. If a call fails, continue with the rest and list failures at the end.

### Inventory audit

1. `check_inventory(low_stock_only=True)`.
2. Present a table sorted by quantity ascending: SKU, name, quantity, price. Mark quantity 0 as **out of stock**.
3. If the user gives restock quantities, apply them with `adjust_stock` (positive delta) and show the new levels.
4. Without instructions, suggest restock amounts only if the user has stated sales rates; otherwise just report.

### Record sales

1. For each item sold, `adjust_stock(sku, -quantity)`.
2. On insufficient stock, do not split or partially fill silently. Report available vs requested and ask how to proceed.
3. After the batch, call `check_inventory(low_stock_only=True)` and mention any product that just dropped into low stock.

### Price changes

1. Resolve SKUs via `check_inventory()`.
2. Compute new prices. For percentage changes, show a preview table: SKU, old price, new price, % change.
3. Apply rule 4, then call `update_price` per product.
4. Summarize from the returned `old_price` / `new_price` values.
5. For "psychological" pricing requests (e.g. end in .99), round to the nearest `.99` below the computed price unless the user says otherwise.

## Output style

- Use a compact table for 3+ products; plain sentences for 1-2.
- Format prices as `€24.99`.
- End multi-step operations with a one-line summary: what changed, what was skipped, what needs the user's decision.
