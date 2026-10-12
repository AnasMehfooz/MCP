"""FastAPI Engineer: REST adapter over the service layer.

Not required for the Claude Desktop loop (the MCP server talks to the service layer directly),
but it exposes the same store to a future web frontend, scripts or webhooks.

Run: uvicorn store.api:app --reload   ->  http://127.0.0.1:8000/docs
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session

from store import services
from store.db import init_db, session_scope
from store.schemas import PriceChange, PriceUpdate, ProductCreate, ProductOut, StockAdjustment


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Headless AI Store", version="0.1.0", lifespan=lifespan)


def get_session() -> Iterator[Session]:
    with session_scope() as session:
        yield session


_STATUS = {
    services.ProductNotFound: status.HTTP_404_NOT_FOUND,
    services.DuplicateSku: status.HTTP_409_CONFLICT,
    services.InsufficientStock: status.HTTP_409_CONFLICT,
}


def _http(exc: services.StoreError) -> HTTPException:
    return HTTPException(_STATUS.get(type(exc), status.HTTP_400_BAD_REQUEST), str(exc))


@app.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, session: Session = Depends(get_session)) -> ProductOut:
    try:
        return services.add_product(session, data)
    except services.StoreError as exc:
        raise _http(exc) from exc


@app.get("/products", response_model=list[ProductOut])
def list_products(low_stock_only: bool = False, session: Session = Depends(get_session)) -> list[ProductOut]:
    return services.list_products(session, low_stock_only=low_stock_only)


@app.get("/products/{sku}", response_model=ProductOut)
def get_product(sku: str, session: Session = Depends(get_session)) -> ProductOut:
    try:
        return services.get_product(session, sku)
    except services.StoreError as exc:
        raise _http(exc) from exc


@app.patch("/products/{sku}/price", response_model=PriceChange)
def update_price(sku: str, body: PriceUpdate, session: Session = Depends(get_session)) -> PriceChange:
    try:
        return services.update_price(session, sku, body.price)
    except services.StoreError as exc:
        raise _http(exc) from exc


@app.post("/products/{sku}/stock", response_model=ProductOut)
def adjust_stock(sku: str, body: StockAdjustment, session: Session = Depends(get_session)) -> ProductOut:
    try:
        return services.adjust_stock(session, sku, body.delta)
    except services.StoreError as exc:
        raise _http(exc) from exc
