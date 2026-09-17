"""Bar content fingerprints must never substitute for canonical observation identity."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import Engine, select

from packages.database.models import Asset, ImportError, PriceBar, Provider, ProviderAssetMapping
from packages.database.session import make_session_factory, session_scope
from packages.market_data.ingestion import create_import_job, run_import_job
from packages.market_data.real_providers import MassiveBasicAdapter
from packages.market_data.registry import ProviderRegistry

EVENT = datetime(2026, 8, 20, 20, tzinfo=UTC)


@pytest.mark.parametrize("symbols", [["AAPL"], ["AAPL", "MSFT"], ["AAPL", "MSFT", "GOOG"]])
def test_identical_content_is_idempotent_only_within_bar_identity(
    engine: Engine,
    symbols: list[str],
) -> None:
    factory = make_session_factory(engine)
    registry = ProviderRegistry()
    row = {"t": int(EVENT.timestamp() * 1000), "o": 100, "h": 103, "l": 99, "c": 102, "v": 1000}
    registry.register(
        MassiveBasicAdapter(
            "fixture-only",
            requests_per_minute=100,
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"results": [row]})),
        )
    )
    with session_scope(factory) as session:
        provider = session.scalar(select(Provider).where(Provider.code == "massive"))
        assert provider is not None
        provider.is_enabled = True
        provider_id = provider.id
    original = {}
    for attempt in range(2):
        with session_scope(factory) as session:
            job = create_import_job(
                session,
                provider_code="massive",
                symbols=symbols,
                mode="full",
                start=EVENT - timedelta(days=1),
                end=EVENT + timedelta(days=1),
            )
            run_import_job(session, job, registry)
            assert job.status == "succeeded"
            assert job.records_inserted == (len(symbols) if attempt == 0 else 0)
            assert job.records_skipped == (0 if attempt == 0 else len(symbols))
        with session_scope(factory) as session:
            bars = session.scalars(
                select(PriceBar).where(PriceBar.provider_id == provider_id)
            ).all()
            assert len(bars) == len(symbols)
            assert len({bar.asset_id for bar in bars}) == len(symbols)
            # Identical content hashes are intentional: the identity lookup disambiguates.
            assert len({bar.checksum for bar in bars}) == 1
            current = {
                bar.id: (bar.asset_id, bar.checksum, bar.event_time, bar.close) for bar in bars
            }
            if attempt == 0:
                original = current
            else:
                assert current == original
    # A new date is a different bar even when every market value is unchanged.
    row["t"] = int((EVENT - timedelta(days=1)).timestamp() * 1000)
    with session_scope(factory) as session:
        job = create_import_job(
            session,
            provider_code="massive",
            symbols=symbols,
            mode="full",
            start=EVENT - timedelta(days=2),
            end=EVENT + timedelta(days=1),
        )
        run_import_job(session, job, registry)
        assert job.status == "succeeded" and job.records_inserted == len(symbols)
    # Existing correction semantics preserve canonical values and record conflicts.
    row["t"] = int(EVENT.timestamp() * 1000)
    row["c"] = 101
    with session_scope(factory) as session:
        job = create_import_job(
            session,
            provider_code="massive",
            symbols=symbols,
            mode="full",
            start=EVENT - timedelta(days=1),
            end=EVENT + timedelta(days=1),
        )
        run_import_job(session, job, registry)
        assert job.records_inserted == 0 and job.records_skipped == len(symbols)
        errors = session.scalars(select(ImportError).where(ImportError.job_id == job.id)).all()
        assert len(errors) == len(symbols)
        assert all(error.error_code == "conflicting_reimport" for error in errors)
    with session_scope(factory) as session:
        bars = session.scalars(select(PriceBar).where(PriceBar.provider_id == provider_id)).all()
        assert len(bars) == len(symbols) * 2
        assert all(bar.close == Decimal("102") for bar in bars)
        assert all(
            (bar.asset_id, bar.checksum, bar.event_time, bar.close) == original[bar.id]
            for bar in bars
            if bar.id in original
        )


def test_provider_alias_resolves_canonical_asset_identity(engine: Engine) -> None:
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        provider = session.scalar(select(Provider).where(Provider.code == "massive"))
        assert provider is not None
        provider.is_enabled = True
        provider_id = provider.id
        for canonical, alias in [("CANONA", "ALIASA"), ("CANONB", "ALIASB")]:
            asset = Asset(
                symbol=canonical,
                name="Same display metadata",
                asset_type="equity",
                exchange="US",
                currency="USD",
            )
            session.add(asset)
            session.flush()
            session.add(
                ProviderAssetMapping(
                    provider_id=provider.id,
                    asset_id=asset.id,
                    provider_symbol=alias,
                    source="massive",
                )
            )
    registry = ProviderRegistry()
    registry.register(
        MassiveBasicAdapter(
            "fixture-only",
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
    with session_scope(factory) as session:
        job = create_import_job(
            session,
            provider_code="massive",
            symbols=["ALIASA", "ALIASB"],
            mode="full",
            start=EVENT - timedelta(days=1),
            end=EVENT + timedelta(days=1),
        )
        run_import_job(session, job, registry)
        assert job.status == "succeeded" and job.records_inserted == 2
    with session_scope(factory) as session:
        bars = session.scalars(select(PriceBar).where(PriceBar.provider_id == provider_id)).all()
        assert {bar.asset.symbol for bar in bars} == {"CANONA", "CANONB"}
        assert {bar.original_symbol for bar in bars} == {"ALIASA", "ALIASB"}
        assert len({bar.asset_id for bar in bars}) == 2
        assert len({bar.checksum for bar in bars}) == 1
        assert session.scalar(select(Asset).where(Asset.symbol.in_(["ALIASA", "ALIASB"]))) is None
