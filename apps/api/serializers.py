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
from packages.core.time import utc_now
from packages.database.models import Asset, AssetCapability, PriceBar, Watchlist


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


def _market_state(
    session: Session,
    asset_id: object,
    bar: PriceBar | None,
    capability_record: AssetCapability | None = None,
    lookup_capability: bool = True,
) -> tuple[str, str, str, str | None]:
    capability = capability_record
    if capability is None and lookup_capability:
        capability = session.scalar(
            select(AssetCapability)
            .where(AssetCapability.asset_id == asset_id)
            .order_by(desc(AssetCapability.as_of_time))
            .limit(1)
        )
    if bar is None:
        return (
            capability.status if capability else "UNAVAILABLE",
            "UNAVAILABLE",
            capability.feed_type if capability else "UNAVAILABLE",
            capability.provider_code if capability else None,
        )
    age_days = (utc_now() - bar.event_time).total_seconds() / 86_400
    freshness = "DEMO" if bar.is_demonstration_data else "STALE" if age_days > 3 else "CURRENT"
    feed = (
        "DEMO"
        if bar.is_demonstration_data
        else capability.feed_type
        if capability
        else "END_OF_DAY"
    )
    return (
        capability.status if capability else "HISTORICAL_AVAILABLE",
        freshness,
        feed,
        capability.provider_code if capability else bar.data_source.name,
    )


def serialize_asset(
    session: Session,
    asset: Asset,
    *,
    bar: PriceBar | None = None,
    capability_record: AssetCapability | None = None,
    lookup_bar: bool = True,
    lookup_capability: bool = True,
) -> AssetSummary:
    if bar is None and lookup_bar:
        bar = latest_bar(session, asset.id)
    capability, freshness, feed, provider = _market_state(
        session, asset.id, bar, capability_record, lookup_capability
    )
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
        capability=capability,
        freshness=freshness,
        feed=feed,
        provider=provider,
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
        prior = session.scalar(
            select(PriceBar)
            .where(PriceBar.asset_id == link.asset_id)
            .order_by(desc(PriceBar.event_time))
            .offset(1)
            .limit(1)
        )
        capability, freshness, feed, provider = _market_state(session, link.asset_id, bar)
        daily_move = (
            ((bar.close / prior.close) - 1) * 100 if bar and prior and prior.close else None
        )
        assets.append(
            WatchlistAssetResponse(
                symbol=link.asset.symbol,
                name=link.asset.name,
                added_at=link.added_at,
                latest_price=bar.close if bar else None,
                latest_price_time=bar.event_time if bar else None,
                is_demonstration_data=bar.is_demonstration_data if bar else None,
                daily_move_pct=daily_move,
                freshness=freshness,
                source=provider,
                feed=feed,
                capability=capability,
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
