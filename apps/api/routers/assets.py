from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from apps.api.schemas import AssetPage, AssetSummary, PricePage
from apps.api.serializers import page_info, serialize_asset, serialize_price
from packages.database.models import Asset, PriceBar

router = APIRouter(prefix="/assets", tags=["assets"])


def _find_asset(session: Session, symbol: str) -> Asset:
    normalized = symbol.strip().upper()
    asset = session.scalar(select(Asset).where(Asset.symbol == normalized))
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' was not found")
    return asset


@router.get("", response_model=AssetPage)
def list_assets(
    session: Session = Depends(get_db),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    sort_by: Literal["symbol", "name", "asset_type", "exchange"] = "symbol",
    sort_direction: Literal["asc", "desc"] = "asc",
) -> AssetPage:
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(Asset.symbol.ilike(term), Asset.name.ilike(term)))
    total = session.scalar(select(func.count(Asset.id)).where(*filters)) or 0
    column = getattr(Asset, sort_by)
    ordering = desc(column) if sort_direction == "desc" else asc(column)
    assets = session.scalars(
        select(Asset)
        .where(*filters)
        .order_by(ordering)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AssetPage(
        items=[serialize_asset(session, asset) for asset in assets],
        pagination=page_info(page, page_size, total),
    )


@router.get("/{symbol}", response_model=AssetSummary)
def get_asset(symbol: str, session: Session = Depends(get_db)) -> AssetSummary:
    return serialize_asset(session, _find_asset(session, symbol))


@router.get("/{symbol}/prices", response_model=PricePage)
def list_prices(
    symbol: str,
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=120, ge=1, le=500),
    start: datetime | None = None,
    end: datetime | None = None,
) -> PricePage:
    asset = _find_asset(session, symbol)
    filters = [PriceBar.asset_id == asset.id]
    if start is not None:
        if start.tzinfo is None:
            raise HTTPException(status_code=422, detail="start must include a timezone")
        filters.append(PriceBar.event_time >= start)
    if end is not None:
        if end.tzinfo is None:
            raise HTTPException(status_code=422, detail="end must include a timezone")
        filters.append(PriceBar.event_time <= end)
    total = session.scalar(select(func.count(PriceBar.id)).where(*filters)) or 0
    bars = session.scalars(
        select(PriceBar)
        .where(*filters)
        .order_by(desc(PriceBar.event_time))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PricePage(
        symbol=asset.symbol,
        items=[serialize_price(bar) for bar in bars],
        pagination=page_info(page, page_size, total),
    )
