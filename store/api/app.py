"""FastAPI Engineer: REST adapter over the service layer.

Not required for the Claude Desktop loop (the MCP server talks to the service layer directly),
but it exposes the same store to a future web frontend, scripts or webhooks.

Run: uvicorn store.api.app:app --reload   ->  http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from store.api.routes import products
from store.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Headless AI Store", version="0.1.0", lifespan=lifespan)
app.include_router(products.router)
