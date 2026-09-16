from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select

from apps.api.serializers import serialize_watchlist
from packages.database.models import (
    LEGACY_USER_ID,
    Asset,
    AssetCapability,
    AssetListing,
    ImportJob,
    PriceBar,
    Provider,
    ProviderAssetMapping,
    Watchlist,
    WatchlistAsset,
    Workspace,
)
from packages.database.session import make_session_factory, session_scope
from packages.market_data.ingestion import create_import_job, run_import_job
from packages.market_data.real_providers import MassiveBasicAdapter
from packages.market_data.reference_sources import (
    NasdaqReferenceAdapter,
    reconcile_reference_records,
)
from packages.market_data.registry import ProviderRegistry

REFERENCE = b"""Symbol|Security Name|Market Category|Test Issue|\
Financial Status|Round Lot Size|ETF|NextShares
FIXM|Mapping Regression Inc.|Q|N|N|100|N|N
"""
EVENT = datetime(2026, 8, 20, 20, tzinfo=UTC)


@pytest.mark.parametrize("age_days, expected_freshness", [(1, "CURRENT"), (5, "STALE")])
def test_massive_canonical_provenance_survives_reference_refresh_and_workspaces(
    engine: Engine,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    age_days: int,
    expected_freshness: str,
) -> None:
    monkeypatch.setattr("apps.api.serializers.utc_now", lambda: EVENT + timedelta(days=age_days))
    registry = ProviderRegistry()
    registry.register(
        MassiveBasicAdapter(
            "fixture-only",
            requests_per_minute=10,
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "t": int(EVENT.timestamp() * 1000),
                                "o": 100,
                                "h": 103,
                                "l": 99,
                                "c": 102,
                                "v": 1000,
                            }
                        ]
                    },
                )
            ),
        )
    )
    factory = make_session_factory(engine)
    records = NasdaqReferenceAdapter.parse("nasdaq", REFERENCE)
    with session_scope(factory) as session:
        reconcile_reference_records(session, records, mark_missing_inactive=False)
        asset = session.scalar(select(Asset).where(Asset.symbol == "FIXM"))
        assert asset is not None
        asset_id = asset.id
        provider = session.scalar(select(Provider).where(Provider.code == "massive"))
        assert provider is not None
        provider.is_enabled = True
        provider_id = provider.id
        workspaces = [
            Workspace(name="Mapping A", slug="mapping-a", created_by_user_id=LEGACY_USER_ID),
            Workspace(name="Mapping B", slug="mapping-b", created_by_user_id=LEGACY_USER_ID),
        ]
        session.add_all(workspaces)
        session.flush()
        workspace_ids = [workspace.id for workspace in workspaces]
    job_ids = []
    for index, workspace_id in enumerate(workspace_ids * 2):
        with session_scope(factory) as session:
            session.info["workspace_id"] = workspace_id
            job = create_import_job(
                session,
                provider_code="massive",
                symbols=["FIXM"],
                mode="full",
                start=EVENT - timedelta(days=1),
                end=EVENT + timedelta(days=1),
                idempotency_key=f"mapping-{workspace_id}-{index}",
            )
            run_import_job(session, job, registry)
            assert job.status == "succeeded", job.error_summary
            assert job.records_inserted == (1 if index == 0 else 0)
            assert job.records_skipped == (0 if index == 0 else 1)
            job_ids.append(job.id)
            # Refresh AFTER prices: newer reference evidence must not relabel stored prices.
            reconcile_reference_records(session, records, mark_missing_inactive=False)
    with session_scope(factory) as session:
        mappings = session.scalars(
            select(ProviderAssetMapping).where(
                ProviderAssetMapping.provider_id == provider_id,
                ProviderAssetMapping.asset_id == asset_id,
            )
        ).all()
        assert len(mappings) == 1
        assert mappings[0].source == "massive" and mappings[0].provider_symbol == "FIXM"
        bars = session.scalars(select(PriceBar).where(PriceBar.asset_id == asset_id)).all()
        assert len(bars) == 1
        bar = bars[0]
        assert bar.provider_id == provider_id and bar.import_job_id == job_ids[0]
        assert bar.raw_provider_metadata["provider"] == "massive"
        assert bar.data_source.name == "provider:massive" and bar.checksum
        assert not bar.is_demonstration_data
        capabilities = session.scalars(
            select(AssetCapability).where(
                AssetCapability.asset_id == asset_id,
            )
        ).all()
        assert len(capabilities) == 2
        historical = next(row for row in capabilities if row.capability == "HISTORICAL")
        reference = next(row for row in capabilities if row.capability == "REFERENCE")
        assert historical.provider_code == "massive"
        assert historical.status == "HISTORICAL_AVAILABLE"
        assert historical.feed_type == "END_OF_DAY" and historical.as_of_time == EVENT
        assert historical.details["bar_id"] == str(bar.id)
        assert reference.provider_code == records[0].source
        assert reference.feed_type == "REFERENCE" and reference.status == "REFERENCE_AVAILABLE"
        listing = session.scalar(select(AssetListing).where(AssetListing.asset_id == asset_id))
        assert listing is not None and listing.source == records[0].source
        assert session.scalar(select(func.count(Asset.id)).where(Asset.symbol == "FIXM")) == 1
    for workspace_id in workspace_ids:
        with session_scope(factory) as session:
            session.info["workspace_id"] = workspace_id
            jobs = session.scalars(select(ImportJob).where(ImportJob.id.in_(job_ids))).all()
            assert len(jobs) == 2 and all(job.workspace_id == workspace_id for job in jobs)
            watchlist = Watchlist(name="Massive evidence", workspace_id=workspace_id)
            session.add(watchlist)
            session.flush()
            session.add(WatchlistAsset(watchlist_id=watchlist.id, asset_id=asset_id))
            session.flush()
            item = serialize_watchlist(session, watchlist).assets[0]
            assert item.source == "massive" and item.feed == "END_OF_DAY"
            assert item.freshness == expected_freshness and item.is_demonstration_data is False
    for url in ("/api/v1/assets/FIXM", "/api/v1/assets?search=FIXM"):
        response = client.get(url)
        assert response.status_code == 200
        payload = response.json()
        item = payload["items"][0] if "items" in payload else payload
        assert item["provider"] == "massive"
        assert item["feed"] == "END_OF_DAY"
        assert item["capability"] == "HISTORICAL_AVAILABLE"
        assert item["freshness"] == expected_freshness
        assert item["is_demonstration_data"] is False
    prices = client.get("/api/v1/assets/FIXM/prices").json()
    assert prices["pagination"]["total"] == 1
    assert prices["items"][0]["source_name"] == "provider:massive"
