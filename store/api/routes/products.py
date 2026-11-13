"""Product routes: the REST twin of the four MCP tools."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from store.api.deps import get_session, get_store_id
from store.catalog import services
from store.catalog.schemas import PriceChange, PriceUpdate, ProductCreate, ProductOut, StockAdjustment
from store.errors import DuplicateSku, InsufficientStock, ProductNotFound, StoreError

router = APIRouter()

_STATUS = {
    ProductNotFound: status.HTTP_404_NOT_FOUND,
    DuplicateSku: status.HTTP_409_CONFLICT,
    InsufficientStock: status.HTTP_409_CONFLICT,
}


def _http(exc: StoreError) -> HTTPException:
    return HTTPException(_STATUS.get(type(exc), status.HTTP_400_BAD_REQUEST), str(exc))


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    data: ProductCreate, session: Session = Depends(get_session), store_id: UUID = Depends(get_store_id)
) -> ProductOut:
    try:
        return services.add_product(session, store_id, data)
    except StoreError as exc:
        raise _http(exc) from exc


@router.get("/products", response_model=list[ProductOut])
def list_products(
    low_stock_only: bool = False, session: Session = Depends(get_session), store_id: UUID = Depends(get_store_id)
) -> list[ProductOut]:
    return services.list_products(session, store_id, low_stock_only=low_stock_only)


@router.get("/products/{sku}", response_model=ProductOut)
def get_product(
    sku: str, session: Session = Depends(get_session), store_id: UUID = Depends(get_store_id)
) -> ProductOut:
    try:
        return services.get_product(session, store_id, sku)
    except StoreError as exc:
        raise _http(exc) from exc


@router.patch("/products/{sku}/price", response_model=PriceChange)
def update_price(
    sku: str, body: PriceUpdate, session: Session = Depends(get_session), store_id: UUID = Depends(get_store_id)
) -> PriceChange:
    try:
        return services.update_price(session, store_id, sku, body.price)
    except StoreError as exc:
        raise _http(exc) from exc


@router.post("/products/{sku}/stock", response_model=ProductOut)
def adjust_stock(
    sku: str,
    body: StockAdjustment,
    session: Session = Depends(get_session),
    store_id: UUID = Depends(get_store_id),
) -> ProductOut:
    try:
        return services.adjust_stock(session, store_id, sku, body.delta)
    except StoreError as exc:
        raise _http(exc) from exc
