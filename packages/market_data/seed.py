from __future__ import annotations

import hashlib
import math
import random
import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.database.models import Asset, DataIngestionRun, DataSource, PriceBar
from packages.market_data.platform_seed import provider_id, seed_market_data_platform

DEMO_NAMESPACE = uuid.UUID("f5857027-d790-43ae-8ff0-e334528cd81a")
DEMO_SOURCE_ID = uuid.uuid5(DEMO_NAMESPACE, "synthetic-demonstration-v1")
BAR_COUNT_PER_ASSET = 120

ASSETS: tuple[dict[str, str | None | float], ...] = (
    {
        "symbol": "SPY",
        "name": "SPDR S&P 500 ETF Trust",
        "asset_type": "ETF",
        "exchange": "NYSE Arca",
        "sector": None,
        "industry": "Broad Market ETF",
        "base": 475.0,
    },
    {
        "symbol": "QQQ",
        "name": "Invesco QQQ Trust",
        "asset_type": "ETF",
        "exchange": "NASDAQ",
        "sector": None,
        "industry": "Technology Growth ETF",
        "base": 410.0,
    },
    {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "asset_type": "Stock",
        "exchange": "NASDAQ",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "base": 185.0,
    },
    {
        "symbol": "MSFT",
        "name": "Microsoft Corporation",
        "asset_type": "Stock",
        "exchange": "NASDAQ",
        "sector": "Technology",
        "industry": "Software",
        "base": 405.0,
    },
    {
        "symbol": "NVDA",
        "name": "NVIDIA Corporation",
        "asset_type": "Stock",
        "exchange": "NASDAQ",
        "sector": "Technology",
        "industry": "Semiconductors",
        "base": 125.0,
    },
    {
        "symbol": "AMZN",
        "name": "Amazon.com, Inc.",
        "asset_type": "Stock",
        "exchange": "NASDAQ",
        "sector": "Consumer Cyclical",
        "industry": "Internet Retail",
        "base": 180.0,
    },
    {
        "symbol": "GOOGL",
        "name": "Alphabet Inc.",
        "asset_type": "Stock",
        "exchange": "NASDAQ",
        "sector": "Communication Services",
        "industry": "Internet Content",
        "base": 165.0,
    },
    {
        "symbol": "META",
        "name": "Meta Platforms, Inc.",
        "asset_type": "Stock",
        "exchange": "NASDAQ",
        "sector": "Communication Services",
        "industry": "Internet Content",
        "base": 485.0,
    },
    {
        "symbol": "TSLA",
        "name": "Tesla, Inc.",
        "asset_type": "Stock",
        "exchange": "NASDAQ",
        "sector": "Consumer Cyclical",
        "industry": "Auto Manufacturers",
        "base": 225.0,
    },
)


def _business_days(count: int) -> list[datetime]:
    day = datetime(2025, 1, 2, 21, 0, tzinfo=UTC)
    values: list[datetime] = []
    while len(values) < count:
        if day.weekday() < 5:
            values.append(day)
        day += timedelta(days=1)
    return values


def _money(value: float) -> Decimal:
    return Decimal(f"{value:.6f}")


def _bars_for(asset: Asset, source: DataSource, seed_index: int) -> list[PriceBar]:
    rng = random.Random(20250102 + seed_index)
    base_price = ASSETS[seed_index]["base"]
    if not isinstance(base_price, float):
        raise TypeError("synthetic asset base price must be a float")
    prior_close = base_price
    bars: list[PriceBar] = []
    for index, event_time in enumerate(_business_days(BAR_COUNT_PER_ASSET)):
        cycle = math.sin((index + seed_index * 2) / 11) * 0.005
        move = 0.0007 + cycle + rng.uniform(-0.012, 0.012)
        open_price = prior_close * (1 + rng.uniform(-0.004, 0.004))
        close = max(1.0, prior_close * (1 + move))
        high = max(open_price, close) * (1 + rng.uniform(0.002, 0.012))
        low = min(open_price, close) * (1 - rng.uniform(0.002, 0.012))
        publication_time = event_time + timedelta(minutes=10)
        retrieval_time = datetime.combine(
            (event_time + timedelta(days=1)).date(), time(2, 0), tzinfo=UTC
        )
        canonical = (
            f"{asset.symbol}|1d|{event_time.isoformat()}|{open_price:.6f}|{high:.6f}|"
            f"{low:.6f}|{close:.6f}|{int(1_000_000 + rng.random() * 90_000_000)}"
        )
        volume = int(canonical.rsplit("|", maxsplit=1)[-1])
        bars.append(
            PriceBar(
                id=uuid.uuid5(DEMO_NAMESPACE, f"{asset.symbol}:1d:{event_time.isoformat()}"),
                asset_id=asset.id,
                interval="1d",
                event_time=event_time,
                publication_time=publication_time,
                effective_time=event_time,
                retrieval_time=retrieval_time,
                open=_money(open_price),
                high=_money(high),
                low=_money(low),
                close=_money(close),
                adjusted_close=_money(close),
                volume=volume,
                data_source_id=source.id,
                provider_id=provider_id("synthetic"),
                original_symbol=asset.symbol,
                adjustment_status="unadjusted",
                checksum=hashlib.sha256(canonical.encode()).hexdigest(),
                record_version=1,
                is_demonstration_data=True,
                created_at=retrieval_time,
            )
        )
        prior_close = close
    return bars


def seed_demonstration_data(session: Session) -> dict[str, int]:
    """Idempotently seed stable, explicitly synthetic research data."""

    seed_market_data_platform(session)
    source = session.get(DataSource, DEMO_SOURCE_ID)
    if source is None:
        source = DataSource(
            id=DEMO_SOURCE_ID,
            name="Deterministic Synthetic Demonstration Provider",
            provider_type="synthetic",
            is_enabled=True,
            health="healthy",
            last_successful_retrieval=datetime(2025, 6, 20, 2, 0, tzinfo=UTC),
            license_notes="Generated locally for demonstration; not licensed market data.",
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        session.add(source)

    inserted_assets = 0
    inserted_bars = 0
    for index, definition in enumerate(ASSETS):
        symbol = str(definition["symbol"])
        asset = session.scalar(select(Asset).where(Asset.symbol == symbol))
        if asset is None:
            asset = Asset(
                id=uuid.uuid5(DEMO_NAMESPACE, f"asset:{symbol}"),
                symbol=symbol,
                name=str(definition["name"]),
                asset_type=str(definition["asset_type"]),
                exchange=str(definition["exchange"]),
                currency="USD",
                sector=definition["sector"] if isinstance(definition["sector"], str) else None,
                industry=str(definition["industry"]),
                is_active=True,
                created_at=datetime(2025, 1, 1, tzinfo=UTC),
                updated_at=datetime(2025, 1, 1, tzinfo=UTC),
            )
            session.add(asset)
            session.flush()
            inserted_assets += 1
        existing_count = session.scalar(
            select(func.count(PriceBar.id)).where(
                PriceBar.asset_id == asset.id, PriceBar.data_source_id == source.id
            )
        )
        if existing_count == 0:
            bars = _bars_for(asset, source, index)
            session.add_all(bars)
            inserted_bars += len(bars)

    session.flush()
    run_id = uuid.uuid5(DEMO_NAMESPACE, "ingestion-run-v1")
    if session.get(DataIngestionRun, run_id) is None:
        session.add(
            DataIngestionRun(
                id=run_id,
                data_source_id=source.id,
                status="succeeded",
                started_at=datetime(2025, 6, 20, 1, 59, tzinfo=UTC),
                completed_at=datetime(2025, 6, 20, 2, 0, tzinfo=UTC),
                records_processed=len(ASSETS) * BAR_COUNT_PER_ASSET,
            )
        )
    from packages.strategies.seed import seed_builtin_strategies

    seed_builtin_strategies(session)
    return {"assets_inserted": inserted_assets, "bars_inserted": inserted_bars}
