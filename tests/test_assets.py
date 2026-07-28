import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError

from packages.database.models import Asset, PriceBar
from packages.database.session import make_session_factory, session_scope


def test_asset_listing_and_pagination(client: TestClient) -> None:
    response = client.get("/api/v1/assets?page=2&page_size=4")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 4
    assert body["pagination"] == {"page": 2, "page_size": 4, "total": 9, "pages": 3}


def test_asset_lookup_normalizes_symbol(client: TestClient) -> None:
    response = client.get("/api/v1/assets/aapl")
    assert response.status_code == 200
    assert response.json()["symbol"] == "AAPL"


def test_asset_search_and_sort(client: TestClient) -> None:
    body = client.get("/api/v1/assets?search=apple&sort_by=name&sort_direction=desc").json()
    assert [item["symbol"] for item in body["items"]] == ["AAPL"]


def test_invalid_asset(client: TestClient) -> None:
    response = client.get("/api/v1/assets/NOPE")
    assert response.status_code == 404
    assert "NOPE" in response.json()["detail"]


def test_price_listing_and_provenance(client: TestClient) -> None:
    response = client.get("/api/v1/assets/SPY/prices?page_size=5")
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 120
    assert len(body["items"]) == 5
    assert body["items"][0]["is_demonstration_data"] is True
    assert body["items"][0]["source_name"].startswith("Deterministic")
    assert all(
        body["items"][0][field].endswith("Z")
        for field in ["event_time", "publication_time", "effective_time", "retrieval_time"]
    )


def test_price_range_requires_timezone(client: TestClient) -> None:
    response = client.get("/api/v1/assets/SPY/prices?start=2025-01-01T00:00:00")
    assert response.status_code == 422
    assert "timezone" in response.json()["detail"]


def test_duplicate_price_bar_prevention(engine: Engine) -> None:
    factory = make_session_factory(engine)
    with pytest.raises(IntegrityError), session_scope(factory) as session:
        original = session.scalar(select(PriceBar).limit(1))
        assert original is not None
        session.add(
            PriceBar(
                id=uuid.uuid4(),
                asset_id=original.asset_id,
                interval=original.interval,
                event_time=original.event_time,
                publication_time=original.publication_time,
                effective_time=original.effective_time,
                retrieval_time=original.retrieval_time,
                open=original.open,
                high=original.high,
                low=original.low,
                close=original.close,
                adjusted_close=original.adjusted_close,
                volume=original.volume,
                data_source_id=original.data_source_id,
                is_demonstration_data=True,
            )
        )


def test_utc_timestamp_handling(engine: Engine) -> None:
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        bar = session.scalar(select(PriceBar).limit(1))
        assert bar is not None and bar.event_time.tzinfo is not None
        assert bar.event_time.utcoffset().total_seconds() == 0


def test_asset_cascade_deletes_prices(engine: Engine) -> None:
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        asset = session.scalar(select(Asset).where(Asset.symbol == "TSLA"))
        assert asset is not None
        asset_id = asset.id
        session.delete(asset)
    with session_scope(factory) as session:
        assert (
            session.scalar(select(func.count(PriceBar.id)).where(PriceBar.asset_id == asset_id))
            == 0
        )
