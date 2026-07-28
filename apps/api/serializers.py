from math import ceil

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.schemas import (
    AssetSummary,
    PageInfo,
    PriceBarResponse,
    WatchlistAssetResponse,
    WatchlistResponse,
)
from packages.database.models import Asset, PriceBar, Watchlist


def page_info(page: int, page_size: int, total: int) -> PageInfo:
    return PageInfo(
        page=page, page_size=page_size, total=total, pages=ceil(total / page_size) if total else 0
    )


def latest_bar(session: Session, asset_id: object) -> PriceBar | None:
    return session.scalar(
        select(PriceBar)
        .where(PriceBar.asset_id == asset_id)
        .order_by(desc(PriceBar.event_time))
        .limit(1)
    )


def serialize_asset(session: Session, asset: Asset) -> AssetSummary:
    bar = latest_bar(session, asset.id)
    return AssetSummary(
        id=asset.id,
        symbol=asset.symbol,
        name=asset.name,
        asset_type=asset.asset_type,
        exchange=asset.exchange,
        currency=asset.currency,
        sector=asset.sector,
        industry=asset.industry,
        is_active=asset.is_active,
        latest_price=bar.close if bar else None,
        latest_price_time=bar.event_time if bar else None,
        is_demonstration_data=bar.is_demonstration_data if bar else None,
    )


def serialize_price(bar: PriceBar) -> PriceBarResponse:
    return PriceBarResponse(
        id=bar.id,
        interval=bar.interval,
        event_time=bar.event_time,
        publication_time=bar.publication_time,
        effective_time=bar.effective_time,
        retrieval_time=bar.retrieval_time,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        adjusted_close=bar.adjusted_close,
        volume=bar.volume,
        data_source_id=bar.data_source_id,
        source_name=bar.data_source.name,
        is_demonstration_data=bar.is_demonstration_data,
    )


def serialize_watchlist(session: Session, watchlist: Watchlist) -> WatchlistResponse:
    assets: list[WatchlistAssetResponse] = []
    for link in sorted(watchlist.asset_links, key=lambda item: item.asset.symbol):
        bar = latest_bar(session, link.asset_id)
        assets.append(
            WatchlistAssetResponse(
                symbol=link.asset.symbol,
                name=link.asset.name,
                added_at=link.added_at,
                latest_price=bar.close if bar else None,
                latest_price_time=bar.event_time if bar else None,
                is_demonstration_data=bar.is_demonstration_data if bar else None,
            )
        )
    return WatchlistResponse(
        id=watchlist.id,
        name=watchlist.name,
        description=watchlist.description,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
        assets=assets,
    )
