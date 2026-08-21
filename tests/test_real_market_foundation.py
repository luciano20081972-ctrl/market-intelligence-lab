from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, insert, select

from packages.database.models import (
    Asset,
    AssetListing,
    MarketOperatingState,
    ScheduledTaskDefinition,
)
from packages.database.session import make_session_factory, session_scope
from packages.market_data.operating_modes import determine_operating_mode
from packages.market_data.real_providers import AlpacaBasicAdapter, MassiveBasicAdapter
from packages.market_data.reference_sources import (
    NasdaqReferenceAdapter,
    SecCompanyTickerAdapter,
    reconcile_reference_records,
)
from packages.market_data.types import ProviderRateLimitError

NASDAQ_FIXTURE = b"""Symbol|Security Name|Market Category|Test Issue|\
Financial Status|Round Lot Size|ETF|NextShares
AAPL|Apple Inc. Common Stock|Q|N|N|100|N|N
TEST|Nasdaq Test Issue|Q|Y|N|100|N|N
File Creation Time: 0820202618:00|||||||
"""
OTHER_FIXTURE = b"""ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|\
Round Lot Size|Test Issue|NASDAQ Symbol
SPY|SPDR S&P 500 ETF Trust|P|SPY|Y|100|N|SPY
WXYZW|Example Warrants|N|WXYZW|N|100|N|WXYZW
File Creation Time: 0820202618:00|||||||
"""
SEC_FIXTURE = (
    b'{"fields":["cik","name","ticker","exchange"],'
    b'"data":[[320193,"Apple Inc.","AAPL","Nasdaq"]]}'
)


def test_official_reference_parsers_and_idempotent_reconciliation(engine: Engine) -> None:
    records = NasdaqReferenceAdapter.parse("nasdaq", NASDAQ_FIXTURE)
    records.extend(NasdaqReferenceAdapter.parse("other", OTHER_FIXTURE))
    records.extend(SecCompanyTickerAdapter.parse(SEC_FIXTURE))
    assert {record.symbol for record in records} == {"AAPL", "TEST", "SPY", "WXYZW"}
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        first = reconcile_reference_records(session, records, mark_missing_inactive=False)
        second = reconcile_reference_records(session, records, mark_missing_inactive=False)
        assert first["listings_inserted"] >= 3
        assert second["assets_inserted"] == 0
        assert session.scalar(select(func.count(Asset.id)).where(Asset.symbol == "AAPL")) == 1
        warrant = session.scalar(
            select(AssetListing).where(AssetListing.normalized_symbol == "WXYZW")
        )
        assert warrant is not None and warrant.eligibility_status == "EXCLUDED"


def test_massive_and_alpaca_adapters_enforce_entitlements() -> None:
    massive_payload = {
        "results": [{"t": 1_767_393_000_000, "o": 100, "h": 103, "l": 99, "c": 102, "v": 1000}]
    }
    massive = MassiveBasicAdapter(
        "test-key",
        requests_per_minute=1,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=massive_payload)
        ),
    )
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 5, tzinfo=UTC)
    bars = massive.fetch_historical_bars("AAPL", start, end)
    assert bars[0].raw_metadata == {
        "provider": "massive",
        "feed": "END_OF_DAY",
        "adjusted": True,
    }
    try:
        massive.fetch_historical_bars("AAPL", start, end)
        raise AssertionError("rate limiter did not enforce entitlement")
    except ProviderRateLimitError:
        pass
    alpaca = AlpacaBasicAdapter(
        "key-id",
        "secret",
        realtime_capacity=17,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "bars": [
                        {"t": "2026-01-02T21:00:00Z", "o": 10, "h": 11, "l": 9, "c": 10.5, "v": 50}
                    ]
                },
            )
        ),
    )
    assert alpaca.health()["realtime_feed"] == "LIVE — IEX"
    assert alpaca.health()["realtime_capacity"] == 17
    metadata = alpaca.fetch_historical_bars("SPY", start, end)[0].raw_metadata
    assert metadata is not None and metadata["feed"] == "IEX"


def test_calendar_driven_modes_respect_session_boundaries(engine: Engine) -> None:
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        pre = determine_operating_mode(
            session, at=datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
        )
        market = determine_operating_mode(
            session, at=datetime(2026, 7, 6, 15, 0, tzinfo=UTC)
        )
        assert pre.mode == "PRE_MARKET"
        assert market.mode == "MARKET"
        assert session.scalar(select(func.count(MarketOperatingState.id))) >= 2


def test_generated_5000_security_catalog_search_is_paginated_and_interactive(
    engine: Engine, client: TestClient
) -> None:
    rows = []
    now = datetime(2026, 8, 20, tzinfo=UTC)
    for index in range(5_000):
        rows.append(
            {
                "id": uuid.uuid5(uuid.NAMESPACE_URL, f"mil-generated-{index}"),
                "symbol": f"G{index:04d}",
                "name": f"Generated Research Security {index:04d}",
                "asset_type": "equity",
                "exchange": "NASDAQ" if index % 2 else "NYSE",
                "currency": "USD",
                "sector": None,
                "industry": None,
                "is_active": index != 4_999,
                "created_at": now,
                "updated_at": now,
            }
        )
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        session.execute(insert(Asset), rows)
    started = time.perf_counter()
    response = client.get("/api/v1/assets?search=Research+Security+4321&page_size=10")
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    assert [item["symbol"] for item in response.json()["items"]] == ["G4321"]
    assert elapsed < 1.0
    page = client.get("/api/v1/assets?page=2&page_size=100&active=true").json()
    assert len(page["items"]) == 100
    assert page["pagination"]["total"] >= 5_008


def test_real_market_automation_is_seeded(engine: Engine) -> None:
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        task_types = set(session.scalars(select(ScheduledTaskDefinition.task_type)))
    assert {
        "REFERENCE_UNIVERSE_REFRESH",
        "HISTORICAL_BACKFILL",
        "DYNAMIC_UNIVERSE",
        "MARKET_OPERATING_MODE",
    }.issubset(task_types)
