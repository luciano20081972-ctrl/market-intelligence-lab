"""Persisted failure/recovery invariants; every provider request uses MockTransport."""

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from packages.database.models import (
    Asset,
    AssetCapability,
    AssetListing,
    ImportBatch,
    ImportError,
    ImportJob,
    PriceBar,
    Provider,
    ProviderAssetMapping,
    ProviderRateLimitState,
)
from packages.database.session import make_session_factory, session_scope
from packages.market_data.ingestion import create_import_job, restart_import_job, run_import_job
from packages.market_data.operations import claim_next_job, register_worker
from packages.market_data.real_providers import MassiveBasicAdapter
from packages.market_data.reference_sources import (
    NasdaqReferenceAdapter,
    reconcile_reference_records,
)
from packages.market_data.registry import ProviderRegistry
from packages.market_data.types import ProviderNetworkError, ProviderRateLimitError

EVENT = datetime(2026, 8, 20, 20, tzinfo=UTC)
REFERENCE = (
    b"Symbol|Security Name|Market Category|Test Issue|Financial Status|"
    b"Round Lot Size|ETF|NextShares\n"
    b"ATOMIC|Atomic Inc.|Q|N|N|100|N|N\n"
)


def response(event: datetime = EVENT) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "results": [
                {
                    "t": int(event.timestamp() * 1000),
                    "o": 100,
                    "h": 103,
                    "l": 99,
                    "c": 102,
                    "v": 1000,
                }
            ]
        },
    )


def registry_for(handler) -> ProviderRegistry:  # type: ignore[no-untyped-def]
    registry = ProviderRegistry()
    registry.register(
        MassiveBasicAdapter(
            "fixture-only",
            requests_per_minute=100,
            transport=httpx.MockTransport(handler),
        )
    )
    return registry


def new_job(session: Session, symbols: list[str] | None = None) -> ImportJob:
    return create_import_job(
        session,
        provider_code="massive",
        symbols=symbols or ["ATOMIC"],
        mode="full",
        start=EVENT - timedelta(days=30),
        end=EVENT + timedelta(days=1),
    )


def seed_good(engine: Engine) -> tuple[UUID, UUID, dict[UUID, tuple[object, ...]]]:
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        reconcile_reference_records(
            session,
            NasdaqReferenceAdapter.parse("nasdaq", REFERENCE),
            mark_missing_inactive=False,
        )
        provider = session.scalar(select(Provider).where(Provider.code == "massive"))
        assert provider is not None
        provider.is_enabled = True
        other = session.scalar(select(Provider).where(Provider.code == "alpaca"))
        assert other is not None
        other.health = "healthy"
        job = new_job(session)
        run_import_job(session, job, registry_for(lambda _: response()))
        assert job.status == "succeeded"
        return provider.id, other.id, snapshot(session)


def snapshot(session: Session) -> dict[UUID, tuple[object, ...]]:
    return {
        bar.id: (
            bar.asset_id,
            bar.provider_id,
            bar.data_source_id,
            bar.checksum,
            bar.event_time,
            bar.close,
            bar.is_demonstration_data,
            bar.import_job_id,
        )
        for bar in session.scalars(select(PriceBar))
    }


def assert_preserved(session: Session, prior: dict[UUID, tuple[object, ...]]) -> None:
    assert snapshot(session) == prior
    asset = session.scalar(select(Asset).where(Asset.symbol == "ATOMIC"))
    assert asset is not None
    listing = session.scalar(select(AssetListing).where(AssetListing.asset_id == asset.id))
    assert listing is not None and listing.source == "nasdaq_trader:nasdaq"
    mappings = session.scalars(
        select(ProviderAssetMapping).where(
            ProviderAssetMapping.asset_id == asset.id,
        )
    ).all()
    assert len(mappings) == 1 and mappings[0].source == "massive"
    cap = session.scalar(
        select(AssetCapability).where(
            AssetCapability.asset_id == asset.id,
            AssetCapability.capability == "HISTORICAL",
        )
    )
    assert cap is not None and cap.as_of_time == EVENT and cap.provider_code == "massive"


@pytest.mark.parametrize(
    "failure,classification,health,retry",
    [
        ("401", "access_denied", "degraded", False),
        ("403", "access_denied", "degraded", False),
        ("429", "rate_limited", "degraded", True),
        ("timeout", "network_unavailable", "unavailable", True),
        ("reset", "network_unavailable", "unavailable", True),
        ("json", "schema_mismatch", "degraded", False),
        ("html", "html_access_page", "degraded", False),
        ("empty", "no_data", "degraded", False),
        ("schema", "schema_mismatch", "degraded", False),
    ],
)
def test_failure_persists_and_recovers(
    engine: Engine,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    classification: str,
    health: str,
    retry: bool,
) -> None:
    provider_id, other_id, prior = seed_good(engine)
    factory = make_session_factory(engine)
    monkeypatch.setattr("apps.api.serializers.utc_now", lambda: EVENT + timedelta(days=10))

    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "timeout":
            raise httpx.ReadTimeout("fixture timeout", request=request)
        if failure == "reset":
            raise httpx.ReadError("fixture reset", request=request)
        if failure.isdigit():
            return httpx.Response(int(failure))
        if failure == "json":
            return httpx.Response(200, content=b"{broken")
        if failure == "html":
            return httpx.Response(200, content=b"<html>access denied</html>")
        return httpx.Response(200, json={"results": []} if failure == "empty" else {})

    with session_scope(factory) as session:
        job = new_job(session)
        job_id = job.id
    with session_scope(factory) as session:
        job = session.get(ImportJob, job_id)
        assert job is not None
        run_import_job(session, job, registry_for(handler))
    # New session proves that control-plane evidence survived the outer commit.
    with session_scope(factory) as session:
        job = session.get(ImportJob, job_id)
        assert job is not None and job.status == ("retrying" if retry else "failed")
        assert job.attempt == 1 and job.records_inserted == 0 and job.resume_cursor == {}
        assert (job.next_retry_at is not None) == retry
        if retry:
            assert job.next_retry_at > datetime.now(UTC) + timedelta(seconds=20)
            worker = register_worker(session, "atomicity-worker")
            assert claim_next_job(session, worker) is None
        assert session.get(Provider, provider_id).health == health
        assert session.get(Provider, other_id).health == "healthy"
        error = session.scalar(select(ImportError).where(ImportError.job_id == job_id))
        assert error is not None and error.error_code == classification
        assert error.is_retryable == retry
        rate = session.scalar(
            select(ProviderRateLimitState).where(
                ProviderRateLimitState.provider_id == provider_id,
            )
        )
        assert (rate is not None) == (failure == "429")
        if rate is not None:
            assert rate.rate_limit_events == 1 and rate.reset_at > datetime.now(UTC)
        assert_preserved(session, prior)
    assert client.get("/api/v1/assets/ATOMIC").json()["freshness"] == "STALE"
    providers = client.get("/api/v1/providers").json()["items"]
    assert next(p for p in providers if p["code"] == "massive")["health"] == health
    with session_scope(factory) as session:
        job = session.get(ImportJob, job_id)
        assert job is not None
        restart_import_job(session, job)
        # Merely queuing must not erase the failed observation.
        assert session.get(Provider, provider_id).health == health
        run_import_job(session, job, registry_for(lambda _: response()))
    with session_scope(factory) as session:
        job = session.get(ImportJob, job_id)
        assert job is not None and job.status == "succeeded"
        assert job.next_retry_at is None and job.error_summary is None
        assert session.get(Provider, provider_id).health == "healthy"
        assert session.get(Provider, other_id).health == "healthy"
        assert_preserved(session, prior)
    assert client.get("/api/v1/assets/ATOMIC").json()["freshness"] == "STALE"


def test_first_second_429_and_success_are_atomic(engine: Engine) -> None:
    provider_id, _, prior = seed_good(engine)
    factory = make_session_factory(engine)
    registry = registry_for(lambda _: httpx.Response(429, headers={"Retry-After": "1200"}))
    with session_scope(factory) as session:
        assert session.scalar(select(func.count(ProviderRateLimitState.id))) == 0
        job_id = new_job(session).id
    for attempt in (1, 2):
        before = datetime.now(UTC)
        with session_scope(factory) as session:
            job = session.get(ImportJob, job_id)
            assert job is not None
            run_import_job(session, job, registry)
        with session_scope(factory) as session:
            job = session.get(ImportJob, job_id)
            rate = session.scalar(select(ProviderRateLimitState))
            assert job is not None and rate is not None
            assert job.status == "retrying" and job.attempt == attempt
            assert job.next_retry_at >= before + timedelta(seconds=1200)
            assert rate.rate_limit_events == attempt and rate.last_response_status == 429
            assert rate.reset_at >= before + timedelta(seconds=1200)
            assert rate.requests_remaining == 0
            assert session.get(Provider, provider_id).health == "degraded"
            assert (
                session.scalar(
                    select(func.count(ImportBatch.id)).where(
                        ImportBatch.job_id == job_id,
                    )
                )
                == 1
            )
            assert_preserved(session, prior)
    with session_scope(factory) as session:
        job = session.get(ImportJob, job_id)
        assert job is not None
        run_import_job(session, job, registry_for(lambda _: response()))
    with session_scope(factory) as session:
        job = session.get(ImportJob, job_id)
        rate = session.scalar(select(ProviderRateLimitState))
        assert job is not None and rate is not None
        assert job.status == "succeeded" and job.attempt == 3 and job.records_skipped == 1
        assert job.next_retry_at is None and job.error_summary is None
        assert rate.rate_limit_events == 2 and rate.reset_at is None
        assert rate.requests_remaining is None and rate.last_response_status is None
        assert session.get(Provider, provider_id).health == "healthy"
        assert_preserved(session, prior)


def test_retry_budget_exhausts_without_immediate_queue_claim(engine: Engine) -> None:
    provider_id, _, prior = seed_good(engine)
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        job_id = new_job(session).id
    for attempt in range(1, 4):
        with session_scope(factory) as session:
            job = session.get(ImportJob, job_id)
            assert job is not None
            run_import_job(session, job, registry_for(lambda _: httpx.Response(429)))
        with session_scope(factory) as session:
            job = session.get(ImportJob, job_id)
            assert job is not None and job.attempt == attempt
            assert job.status == ("retrying" if attempt < 3 else "failed")
            if attempt == 3:
                assert job.next_retry_at is None and job.completed_at is not None
            worker = register_worker(session, "retry-budget")
            assert claim_next_job(session, worker) is None
            assert session.get(Provider, provider_id).health == "degraded"
            assert_preserved(session, prior)


@pytest.mark.parametrize("header,minimum", [("1200", 1200), ("bad", 0), ("-1", 0)])
def test_retry_after_adapter_parsing(header: str, minimum: int) -> None:
    adapter = MassiveBasicAdapter(
        "fixture-only",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(429, headers={"Retry-After": header}),
        ),
    )
    with pytest.raises(ProviderRateLimitError) as error:
        adapter.fetch_historical_bars("ATOMIC", EVENT - timedelta(days=1), EVENT)
    assert (error.value.retry_after_seconds or 0) == minimum


def test_http_date_retry_after_is_persisted(engine: Engine) -> None:
    seed_good(engine)
    deadline = (datetime.now(UTC) + timedelta(minutes=20)).replace(microsecond=0)
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        job = new_job(session)
        job_id = job.id
        run_import_job(
            session,
            job,
            registry_for(
                lambda _: httpx.Response(
                    429,
                    headers={"Retry-After": format_datetime(deadline, usegmt=True)},
                )
            ),
        )
    with session_scope(factory) as session:
        job = session.get(ImportJob, job_id)
        state = session.scalar(select(ProviderRateLimitState))
        assert job is not None and state is not None
        assert job.status == "retrying" and job.next_retry_at >= deadline
        assert state.reset_at >= deadline and state.rate_limit_events == 1


def test_normalized_websocket_disconnect_and_reconnect_contract(engine: Engine) -> None:
    # The production adapters expose REST only. This fixture proves shared ingestion's
    # normalized transport-error contract, not a production WebSocket reconnect loop.
    provider_id, other_id, prior = seed_good(engine)
    factory = make_session_factory(engine)

    class StreamFixture(MassiveBasicAdapter):
        connected = False

        def fetch_historical_bars(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            if not self.connected:
                raise ProviderNetworkError("WebSocket fixture disconnected")
            return super().fetch_historical_bars(*args, **kwargs)

    adapter = StreamFixture("fixture-only", transport=httpx.MockTransport(lambda _: response()))
    registry = ProviderRegistry()
    registry.register(adapter)
    with session_scope(factory) as session:
        job = new_job(session)
        job_id = job.id
        run_import_job(session, job, registry)
    with session_scope(factory) as session:
        job = session.get(ImportJob, job_id)
        assert job is not None and job.status == "retrying" and job.next_retry_at is not None
        assert session.get(Provider, provider_id).health == "unavailable"
        assert session.get(Provider, other_id).health == "healthy"
        assert_preserved(session, prior)
        adapter.connected = True
        assert session.get(Provider, provider_id).health == "unavailable"
        run_import_job(session, job, registry)
    with session_scope(factory) as session:
        job = session.get(ImportJob, job_id)
        assert job is not None and job.status == "succeeded" and job.next_retry_at is None
        assert session.get(Provider, provider_id).health == "healthy"
        assert_preserved(session, prior)
