from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from apps.api.dependencies import get_db
from apps.api.schemas import AssetPage, AssetSummary, PricePage
from apps.api.serializers import page_info, serialize_asset, serialize_price
from packages.database.models import Asset, AssetCapability, PriceBar

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
    exchange: str | None = Query(default=None, max_length=32),
    asset_type: str | None = Query(default=None, max_length=32),
    active: bool | None = None,
    capability: str | None = Query(default=None, max_length=40),
) -> AssetPage:
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(Asset.symbol.ilike(term), Asset.name.ilike(term)))
    if exchange:
        filters.append(Asset.exchange == exchange)
    if asset_type:
        filters.append(func.lower(Asset.asset_type) == asset_type.lower())
    if active is not None:
        filters.append(Asset.is_active.is_(active))
    if capability:
        filters.append(
            select(AssetCapability.id)
            .where(
                AssetCapability.asset_id == Asset.id,
                AssetCapability.status == capability,
            )
            .exists()
        )
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
    asset_ids = [asset.id for asset in assets]
    bars_by_asset: dict[object, PriceBar] = {}
    capabilities_by_asset: dict[object, AssetCapability] = {}
    if asset_ids:
        latest_times = (
            select(
                PriceBar.asset_id.label("asset_id"),
                func.max(PriceBar.event_time).label("event_time"),
            )
            .where(PriceBar.asset_id.in_(asset_ids))
            .group_by(PriceBar.asset_id)
            .subquery()
        )
        for bar in session.scalars(
            select(PriceBar)
            .join(
                latest_times,
                (PriceBar.asset_id == latest_times.c.asset_id)
                & (PriceBar.event_time == latest_times.c.event_time),
            )
            .options(selectinload(PriceBar.data_source))
            .order_by(PriceBar.asset_id, PriceBar.id)
        ):
            bars_by_asset.setdefault(bar.asset_id, bar)
        for record in session.scalars(
            select(AssetCapability)
            .where(AssetCapability.asset_id.in_(asset_ids))
            .order_by(AssetCapability.asset_id, desc(AssetCapability.as_of_time))
        ):
            capabilities_by_asset.setdefault(record.asset_id, record)
    return AssetPage(
        items=[
            serialize_asset(
                session,
                asset,
                bar=bars_by_asset.get(asset.id),
                capability_record=capabilities_by_asset.get(asset.id),
                lookup_bar=False,
                lookup_capability=False,
            )
            for asset in assets
        ],
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
