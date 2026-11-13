# 0001: Postgres with pgvector as the only datastore

- Status: accepted
- Date: 2026-11-13 (chosen in the blueprint of 2026-11-06, implemented in migration `0001`)

## Context

v1 kept two tables in a SQLite file, created by `create_all` at startup. v2 needs more than that setup gives:

- **Vector search in three places:** products (`search_catalog`), store pages (the Support agent's source) and memory facts (`recall`), all as bge-m3 embeddings with 1024 dimensions.
- **Several writers at once:** the FastAPI app, the MCP server that Claude Desktop starts, a job worker and Stripe webhooks. Stock decrements must not oversell, and the worker claims jobs with `SELECT … FOR UPDATE SKIP LOCKED`.
- **Tenancy:** every table carries `store_id`, with row-level security as a later option.
- **A schema that changes every phase:** orders, conversations, memory and drafts tables arrive over the coming weeks.
- **One 16 GB laptop** that runs all of it next to Ollama.

## Decision

Postgres 16 with the pgvector extension holds everything: relational data, embeddings (`vector(1024)` columns with HNSW cosine indexes) and the job queue. It runs as one container, `pgvector/pgvector:pg16`. Alembic owns the schema. SQLite support is removed, not kept as a second backend.

## Alternatives

| Option | Why not |
| --- | --- |
| Stay on SQLite and add sqlite-vec | One writer at a time, no row locks, no `SKIP LOCKED`, no row-level security. The job queue and the stock decrement would need locking written in the application. |
| Postgres plus a vector database (ChromaDB, Qdrant) | A second datastore to run and keep consistent. Embeddings would live outside the transaction that changes their row, so every write becomes a dual write, and the `store_id` filter must be enforced in two systems. A demo store has at most a few thousand vectors, far below the size where a dedicated index pays off. |
| Support both SQLite and Postgres through SQLAlchemy | Every query is limited to what both engines share. pgvector operators, JSONB, `FOR UPDATE` and row-level security would each need a fallback, and the tests would pass on an engine that the real system does not use. |

## Consequences

What this buys:

- An embedding is written in the same transaction as its row, and a vector search filters on `store_id` in the same query.
- Row locks exist: `adjust_stock` locks the inventory row, and the job worker can use `SKIP LOCKED`.
- Schema changes are reviewed files. `tests/test_migrations.py` fails when models and migrations disagree.

What it costs:

- Nothing runs without Postgres. Tests, the REST API and the MCP server all need `docker compose up -d postgres`, and v1's zero-setup `uvx` install is gone. The MCP server reports a stopped or unmigrated database as a tool error instead of failing to start.
- RAM is shared with Ollama. The container is capped at 1 GB and used about 40 MB when idle (measured under Linux Docker; Docker Desktop on Windows adds its own overhead).
- The embedding size is part of the schema. Choosing `nomic-embed-text` (768 dimensions) at the Dec 7 decision would mean a migration and re-embedding.
- Tests need a real database. Each test gets its own schema; the suite of 70 tests takes about 5 seconds.
