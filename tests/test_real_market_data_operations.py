from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from sqlalchemy import func, select

from apps.api.routers import operations as operations_router
from packages.core.config import Settings
from packages.database.models import (
    DataSource,
    ExchangeCalendar,
    ImportError,
    ImportJob,
    ImportSchedule,
    JobLease,
    OperationalMetric,
    PriceBar,
    Provider,
    ProviderSymbolMapping,
    ReconciliationIssue,
    ScheduleRun,
    TradingSession,
    WorkerInstance,
)
from packages.database.session import make_session_factory, session_scope
from packages.market_data.adapters import StooqAdapter
from packages.market_data.calendars import generate_maintained_sessions
from packages.market_data.ingestion import create_import_job, run_import_job
from packages.market_data.observability import JsonFormatter, redact
from packages.market_data.operations import (
    claim_next_job,
    execute_claimed_job,
    process_due_schedules,
    recover_abandoned_jobs,
    register_worker,
    renew_lease,
)
from packages.market_data.rate_limit import InProcessRateLimiter
from packages.market_data.reconciliation import preview_reconciliation, run_reconciliation
from packages.market_data.registry import ProviderRegistry
from packages.market_data.types import (
    ProviderContentTypeError,
    ProviderDataError,
    ProviderEncodingError,
    ProviderHtmlResponseError,
    ProviderInvalidDateRangeError,
    ProviderNetworkError,
    ProviderNoDataError,
    ProviderRateLimitError,
    ProviderRejectedRequestError,
    ProviderResponseError,
    ProviderResponseTooLargeError,
    ProviderSchemaError,
    ProviderTemporaryError,
    ProviderUnsupportedSymbolError,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _transport(
    status: int = 200,
    content: bytes | None = None,
    content_type: str | None = "text/csv; charset=utf-8",
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.scheme == "https"
        assert request.url.host == "stooq.com"
        assert request.url.path == "/q/d/l/"
        headers = {"content-type": content_type} if content_type else {}
        return httpx.Response(
            status,
            content=_fixture("stooq_valid.csv") if content is None else content,
            headers=headers,
            request=request,
        )

    return httpx.MockTransport(handler)


def _job(session, *, key: str | None = None) -> ImportJob:  # type: ignore[no-untyped-def]
    return create_import_job(
        session,
        provider_code="synthetic",
        symbols=["AAPL"],
        mode="full",
        start=datetime(2026, 7, 6, tzinfo=UTC),
        end=datetime(2026, 7, 10, 23, 59, tzinfo=UTC),
        idempotency_key=key,
    )


def test_stooq_configuration_symbol_mapping_and_fixture_parsing() -> None:
    adapter = StooqAdapter(transport=_transport())
    assert adapter.normalize_symbol(" AAPL ") == "aapl.us"
    assert adapter.health()["authentication_required"] is False
    records = adapter.fetch_historical_bars(
        "AAPL",
        datetime(2026, 7, 1, tzinfo=UTC),
        datetime(2026, 7, 10, tzinfo=UTC),
    )
    assert len(records) == 3
    assert records[0].provider_symbol == "aapl.us"
    assert records[0].close == Decimal("104")
    assert records[0].event_time == datetime(2026, 7, 6, 20, tzinfo=UTC)
    assert records[0].raw_metadata is not None
    assert len(records[0].checksum) == 64


@pytest.mark.parametrize("symbol", ["AAPL", "MSFT", "SPY", "aapl.us"])
def test_stooq_endpoint_and_supported_symbol_contract(symbol: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        expected_symbol = f"{symbol.removesuffix('.us').lower()}.us"
        assert dict(request.url.params) == {
            "s": expected_symbol,
            "d1": "20260701",
            "d2": "20260710",
            "i": "d",
        }
        return httpx.Response(
            200,
            content=_fixture("stooq_valid.csv"),
            headers={"content-type": "text/csv"},
            request=request,
        )

    records = StooqAdapter(transport=httpx.MockTransport(handler)).fetch_historical_bars(
        symbol,
        datetime(2026, 7, 1, tzinfo=UTC),
        datetime(2026, 7, 10, tzinfo=UTC),
    )
    assert len(records) == 3


@pytest.mark.parametrize("symbol", ["^SPX", "BRK.B", "", "../AAPL"])
def test_stooq_rejects_unconfirmed_symbol_forms(symbol: str) -> None:
    with pytest.raises(ProviderUnsupportedSymbolError):
        StooqAdapter.normalize_symbol(symbol)


def test_stooq_rejects_invalid_date_range_before_network_access() -> None:
    moment = datetime(2026, 7, 1, tzinfo=UTC)
    with pytest.raises(ProviderInvalidDateRangeError) as captured:
        StooqAdapter(transport=_transport()).fetch_historical_bars("AAPL", moment, moment)
    assert captured.value.classification == "invalid_date_range"


def test_stooq_timeout_rate_limit_and_retry_classification() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    dates = (datetime(2026, 7, 1, tzinfo=UTC), datetime(2026, 7, 10, tzinfo=UTC))
    with pytest.raises(ProviderNetworkError, match="timed out"):
        StooqAdapter(transport=httpx.MockTransport(timeout)).fetch_historical_bars("AAPL", *dates)
    with pytest.raises(ProviderRateLimitError):
        StooqAdapter(transport=_transport(429)).fetch_historical_bars("AAPL", *dates)
    with pytest.raises(ProviderTemporaryError, match="503"):
        StooqAdapter(transport=_transport(503)).fetch_historical_bars("AAPL", *dates)


@pytest.mark.parametrize(
    ("fixture", "content_type", "error_type", "classification"),
    [
        ("stooq_empty.txt", "text/plain", ProviderNoDataError, "no_data"),
        (
            "stooq_html_verification.html",
            "text/html",
            ProviderHtmlResponseError,
            "html_access_page",
        ),
        (
            "stooq_unsupported_symbol.txt",
            "text/plain",
            ProviderUnsupportedSymbolError,
            "unsupported_symbol",
        ),
        ("stooq_malformed_schema.csv", "text/csv", ProviderSchemaError, "schema_mismatch"),
        (
            "stooq_invalid_ohlc.csv",
            "text/csv",
            ProviderDataError,
            "malformed_market_data",
        ),
        (
            "stooq_negative_volume.csv",
            "text/csv",
            ProviderDataError,
            "malformed_market_data",
        ),
    ],
)
def test_stooq_classifies_sanitized_response_fixtures(
    fixture: str,
    content_type: str,
    error_type: type[ProviderResponseError],
    classification: str,
) -> None:
    with pytest.raises(error_type) as captured:
        StooqAdapter(
            transport=_transport(content=_fixture(fixture), content_type=content_type)
        ).fetch_historical_bars(
            "AAPL",
            datetime(2026, 7, 1, tzinfo=UTC),
            datetime(2026, 7, 10, tzinfo=UTC),
        )
    assert captured.value.classification == classification
    assert "<!DOCTYPE" not in str(captured.value)
    assert "Verification required" not in str(captured.value)


@pytest.mark.parametrize("fixture", ["stooq_normalized_header.csv", "stooq_bom.csv"])
def test_stooq_accepts_safe_header_and_encoding_normalization(fixture: str) -> None:
    records = StooqAdapter(transport=_transport(content=_fixture(fixture))).fetch_historical_bars(
        "AAPL",
        datetime(2026, 7, 1, tzinfo=UTC),
        datetime(2026, 7, 10, tzinfo=UTC),
    )
    assert len(records) == 1 and records[0].volume == 12345


@pytest.mark.parametrize(
    "content",
    [
        b"Date;Open;High;Low;Close;Volume\n2026-07-06;100;105;99;104;10\n",
        b"Date,Open,High,Low,Close,Volume\n2026-07-06,100,105,99,104,1.5\n",
        b"Date,Open,High,Low,Close,Volume\n2026-07-06,N/D,105,99,104,10\n",
        b"Date,Open,High,Low,Close,Volume\n2026-02-30,100,105,99,104,10\n",
        b"Date,Open,High,Low,Close,Volume\n2026-07-06,NaN,105,99,104,10\n",
        b"Date,Open,High,Low,Close,Volume\n2026-06-30,100,105,99,104,10\n",
        b"Date,Open,High,Low,Close,Close\n2026-07-06,100,105,99,104,10\n",
        (
            b"Date,Open,High,Low,Close,Volume\n"
            b"2026-07-06,100,105,99,104,10\n"
            b"2026-07-06,100,105,99,104,10\n"
        ),
    ],
)
def test_stooq_rejects_unconfirmed_or_invalid_csv_values(content: bytes) -> None:
    with pytest.raises(ProviderResponseError):
        StooqAdapter(transport=_transport(content=content)).fetch_historical_bars(
            "AAPL",
            datetime(2026, 7, 1, tzinfo=UTC),
            datetime(2026, 7, 10, tzinfo=UTC),
        )


def test_stooq_rejects_unsupported_encoding_and_oversized_response() -> None:
    dates = (datetime(2026, 7, 1, tzinfo=UTC), datetime(2026, 7, 10, tzinfo=UTC))
    with pytest.raises(ProviderEncodingError):
        StooqAdapter(transport=_transport(content=b"\xff\xfeinvalid")).fetch_historical_bars(
            "AAPL", *dates
        )
    adapter = StooqAdapter(transport=_transport())
    adapter.max_response_bytes = 10
    with pytest.raises(ProviderResponseTooLargeError):
        adapter.fetch_historical_bars("AAPL", *dates)


def test_stooq_rejects_unexpected_content_type_and_redirect() -> None:
    dates = (datetime(2026, 7, 1, tzinfo=UTC), datetime(2026, 7, 10, tzinfo=UTC))
    with pytest.raises(ProviderContentTypeError):
        StooqAdapter(transport=_transport(content_type="application/json")).fetch_historical_bars(
            "AAPL", *dates
        )
    with pytest.raises(ProviderRejectedRequestError):
        StooqAdapter(transport=_transport(status=302)).fetch_historical_bars("AAPL", *dates)


def test_stooq_health_distinguishes_valid_invalid_no_data_and_unavailable() -> None:
    health_csv = b"Date,Open,High,Low,Close,Volume\n2024-01-02,100,105,99,104,12345\n"
    healthy = StooqAdapter(transport=_transport(content=health_csv)).test_connectivity()
    html = StooqAdapter(
        transport=_transport(
            content=_fixture("stooq_html_verification.html"), content_type="text/html"
        )
    ).test_connectivity()
    no_data = StooqAdapter(
        transport=_transport(content=_fixture("stooq_empty.txt"), content_type="text/plain")
    ).test_connectivity()

    def network_failure(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    unavailable = StooqAdapter(transport=httpx.MockTransport(network_failure)).test_connectivity()
    assert (healthy["status"], healthy["response_classification"]) == (
        "healthy",
        "valid_csv",
    )
    assert (html["status"], html["connectivity"], html["response_classification"]) == (
        "degraded",
        "reachable_invalid",
        "html_access_page",
    )
    assert (no_data["connectivity"], no_data["schema_compatible"]) == (
        "reachable_no_data",
        True,
    )
    assert (unavailable["status"], unavailable["reachable"]) == ("unavailable", False)


def test_stooq_health_api_persists_reachable_invalid_diagnostic(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    registry = ProviderRegistry()
    registry.register(
        StooqAdapter(
            transport=_transport(
                content=_fixture("stooq_html_verification.html"), content_type="text/html"
            )
        ),
        enabled_by_default=True,
    )
    monkeypatch.setattr(operations_router, "default_registry", registry)
    provider = next(
        item
        for item in client.get("/api/v1/providers?page_size=100").json()["items"]
        if item["code"] == "stooq"
    )
    tested = client.post(f"/api/v1/providers/{provider['id']}/test")
    assert tested.status_code == 200
    assert tested.json()["status"] == "degraded"
    assert tested.json()["connectivity"] == "reachable_invalid"
    assert tested.json()["response_classification"] == "html_access_page"
    status = client.get(f"/api/v1/providers/{provider['id']}/status")
    assert status.status_code == 200
    assert status.json()["health"] == "degraded"
    assert status.json()["response_classification"] == "html_access_page"
    assert status.json()["message"] == (
        "Stooq returned an HTML verification or access page instead of market data"
    )


def test_stooq_durable_job_preserves_safe_provider_classification(engine) -> None:  # type: ignore[no-untyped-def]
    registry = ProviderRegistry()
    registry.register(
        StooqAdapter(
            transport=_transport(
                content=_fixture("stooq_html_verification.html"), content_type="text/html"
            )
        ),
        enabled_by_default=True,
    )
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        job = create_import_job(
            session,
            provider_code="stooq",
            symbols=["AAPL"],
            mode="full",
            start=datetime(2026, 7, 1, tzinfo=UTC),
            end=datetime(2026, 7, 10, tzinfo=UTC),
        )
        run_import_job(session, job, registry)
        assert job.status == "failed"
        error = session.scalar(select(ImportError).where(ImportError.job_id == job.id))
        assert error is not None
        assert error.error_code == "html_access_page"
        assert error.payload_summary["provider_classification"] == "html_access_page"
        assert "<!DOCTYPE" not in error.message


def test_import_idempotency_queue_claim_heartbeat_and_metrics(engine) -> None:  # type: ignore[no-untyped-def]
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        job = _job(session, key="same-request")
        duplicate = _job(session, key="same-request")
        assert duplicate.id == job.id
        worker = register_worker(session, "worker-a")
        second_worker = register_worker(session, "worker-b")
        claimed = claim_next_job(session, worker)
        assert claimed is not None
        claimed_job, lease = claimed
        assert claim_next_job(session, second_worker) is None
        old_expiry = lease.expires_at
        renew_lease(session, lease, worker)
        assert lease.expires_at >= old_expiry
        execute_claimed_job(session, claimed_job, lease, worker)
        assert claimed_job.status == "succeeded"
        assert session.scalar(select(func.count(JobLease.id))) == 0
        assert session.scalar(select(func.count(OperationalMetric.id))) == 5
        assert session.scalar(select(func.count(ProviderSymbolMapping.id))) >= 1


def test_expired_lease_recovers_abandoned_job(engine) -> None:  # type: ignore[no-untyped-def]
    factory = make_session_factory(engine)
    current = datetime.now(UTC)
    with session_scope(factory) as session:
        job = _job(session)
        worker = register_worker(session, "recovery-worker")
        claimed = claim_next_job(
            session, worker, lease_seconds=10, now=current - timedelta(minutes=1)
        )
        assert claimed is not None and job.status == "running"
        recovered = recover_abandoned_jobs(session, now=current)
        assert recovered == [job.id]
        assert job.status == "retrying"
        assert worker.status == "unavailable"


def test_schedule_creation_is_persisted_and_deduplicated(engine) -> None:  # type: ignore[no-untyped-def]
    factory = make_session_factory(engine)
    due = datetime.now(UTC) - timedelta(minutes=1)
    with session_scope(factory) as session:
        provider = session.scalar(select(Provider).where(Provider.code == "synthetic"))
        assert provider is not None
        schedule = ImportSchedule(
            provider_id=provider.id,
            name="daily-aapl",
            symbols=["AAPL"],
            date_range_policy={"lookback_days": 5},
            next_run_at=due,
        )
        session.add(schedule)
        session.flush()
        first = process_due_schedules(session, now=datetime.now(UTC))
        second = process_due_schedules(session, now=datetime.now(UTC))
        assert len(first) == 1
        assert second == []
        assert session.scalar(select(func.count(ScheduleRun.id))) == 1
        assert first[0].queue_name == "daily"


def test_maintained_calendar_supports_future_holiday_and_early_close(engine) -> None:  # type: ignore[no-untyped-def]
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        calendar = session.scalar(select(ExchangeCalendar).where(ExchangeCalendar.code == "XNYS"))
        assert calendar is not None
        inserted = generate_maintained_sessions(
            session, calendar, date(2030, 1, 1), date(2030, 12, 31)
        )
        assert inserted > 200
        assert (
            session.scalar(
                select(TradingSession).where(TradingSession.session_date == "2030-07-04")
            )
            is None
        )
        early = session.scalar(
            select(TradingSession).where(TradingSession.session_date == "2030-11-29")
        )
        assert early is not None and early.is_early_close is True
        assert early.open_time.tzinfo is not None and early.close_time.tzinfo is not None


def test_reconciliation_dry_run_persists_without_mutating_prices(engine) -> None:  # type: ignore[no-untyped-def]
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        before = session.scalar(select(func.count(PriceBar.id)))
        preview = preview_reconciliation(session, now=datetime(2025, 7, 1, tzinfo=UTC))
        assert preview["dry_run"] is True
        run = run_reconciliation(session, dry_run=True)
        assert run.status == "succeeded" and run.dry_run is True
        assert session.scalar(select(func.count(PriceBar.id))) == before
        assert session.scalar(select(func.count(ReconciliationIssue.id))) == run.issue_count


def test_conflicting_reimport_is_preserved_and_reported(engine) -> None:  # type: ignore[no-untyped-def]
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        first = _job(session)
        run_import_job(session, first)
        assert first.status == "succeeded"
        original_count = session.scalar(
            select(func.count(PriceBar.id)).where(PriceBar.import_job_id == first.id)
        )
        preserved = session.scalar(
            select(PriceBar).where(PriceBar.import_job_id == first.id).limit(1)
        )
        assert preserved is not None
        preserved.checksum = "0" * 64
        preserved_id = preserved.id
        second = _job(session)
        second.mode = "full"
        run_import_job(session, second)
        assert (
            session.scalar(
                select(func.count(PriceBar.id)).where(PriceBar.import_job_id == second.id)
            )
            == 0
        )
        assert second.records_skipped == original_count
        conflict = session.scalar(
            select(ImportError).where(
                ImportError.job_id == second.id,
                ImportError.error_code == "conflicting_reimport",
            )
        )
        assert conflict is not None
        assert session.get(PriceBar, preserved_id).checksum == "0" * 64


def test_operations_api_health_events_schedules_and_reconciliation(client) -> None:  # type: ignore[no-untyped-def]
    providers = client.get("/api/v1/providers?page_size=100").json()["items"]
    synthetic = next(item for item in providers if item["code"] == "synthetic")
    preview = client.post(
        "/api/v1/import/jobs/preview",
        json={
            "provider_code": "synthetic",
            "symbols": ["AAPL"],
            "start": "2026-07-06T00:00:00Z",
            "end": "2026-07-10T23:59:59Z",
        },
    )
    assert preview.status_code == 200 and preview.json()["can_submit"] is True
    job = client.post(
        "/api/v1/import/jobs",
        headers={"Idempotency-Key": "api-idempotency"},
        json={
            "provider_code": "synthetic",
            "symbols": ["AAPL"],
            "start": "2026-07-06T00:00:00Z",
            "end": "2026-07-10T23:59:59Z",
        },
    )
    assert job.status_code == 201 and job.json()["status"] == "queued"
    job_id = job.json()["id"]
    events = client.get(f"/api/v1/import/jobs/{job_id}/events")
    assert events.status_code == 200 and events.json()[0]["event_type"] == "queued"
    cancelled = client.post(f"/api/v1/import/jobs/{job_id}/cancel")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    schedule = client.post(
        "/api/v1/import/schedules",
        json={
            "provider_id": synthetic["id"],
            "name": "api-daily",
            "symbols": ["AAPL"],
            "next_run_at": "2030-01-01T12:00:00Z",
            "timezone": "America/New_York",
        },
    )
    assert schedule.status_code == 201
    assert client.get("/api/v1/import/schedules").json()[0]["name"] == "api-daily"
    reconciliation = client.post("/api/v1/reconciliation/preview", json={"dry_run": True})
    assert reconciliation.status_code == 200
    health = client.get("/api/v1/operations/health")
    assert health.status_code == 200
    assert health.json()["database"] == "healthy"
    assert client.get("/health/live").json()["version"] == "0.11.0"
    assert client.get("/health/ready").json()["database"] == "healthy"


def test_stooq_fixture_import_is_idempotent_reconciled_and_backtestable(client, engine) -> None:  # type: ignore[no-untyped-def]
    def history(request: httpx.Request) -> httpx.Response:
        provider_symbol = request.url.params["s"]
        current = datetime.strptime(request.url.params["d1"], "%Y%m%d").date()
        finish = datetime.strptime(request.url.params["d2"], "%Y%m%d").date()
        base = 300 if provider_symbol == "spy.us" else 100
        rows = ["Date,Open,High,Low,Close,Volume"]
        index = 0
        while current <= finish:
            if current.weekday() < 5:
                price = base + index
                rows.append(
                    f"{current.isoformat()},{price},{price + 2},{price - 1},"
                    f"{price + 1},{10000 + index}"
                )
                index += 1
            current += timedelta(days=1)
        return httpx.Response(
            200,
            content=("\n".join(rows) + "\n").encode(),
            headers={"content-type": "text/csv"},
            request=request,
        )

    registry = ProviderRegistry()
    registry.register(StooqAdapter(transport=httpx.MockTransport(history)), enabled_by_default=True)
    factory = make_session_factory(engine)
    start = datetime(2026, 7, 6, tzinfo=UTC)
    end = datetime(2026, 8, 14, 23, 59, tzinfo=UTC)
    with session_scope(factory) as session:
        provider = session.scalar(select(Provider).where(Provider.code == "stooq"))
        assert provider is not None
        first = create_import_job(
            session,
            provider_code="stooq",
            symbols=["AAPL", "SPY"],
            mode="full",
            start=start,
            end=end,
            adjustment_preference="provider_default",
        )
        run_import_job(session, first, registry)
        assert first.status == "succeeded"
        assert first.records_inserted == 60
        assert (
            session.scalar(
                select(func.count(PriceBar.id)).where(
                    PriceBar.import_job_id == first.id,
                    PriceBar.is_demonstration_data.is_(False),
                )
            )
            == 60
        )
        assert (
            session.scalar(
                select(func.count(ProviderSymbolMapping.id)).where(
                    ProviderSymbolMapping.provider_id == provider.id
                )
            )
            == 2
        )
        second = create_import_job(
            session,
            provider_code="stooq",
            symbols=["AAPL", "SPY"],
            mode="full",
            start=start,
            end=end,
            adjustment_preference="provider_default",
        )
        run_import_job(session, second, registry)
        assert second.status == "succeeded"
        assert second.records_inserted == 0 and second.records_skipped == 60
        reconciliation = run_reconciliation(
            session, provider_id=provider.id, symbols=["AAPL", "SPY"], dry_run=True
        )
        assert reconciliation.status == "succeeded"
        assert reconciliation.records_checked == 60
        first_id = first.id

    strategies = client.get("/api/v1/strategies").json()["items"]
    version_id = next(
        item["latest_version"]["id"]
        for item in strategies
        if item["strategy_type"] == "buy_and_hold"
    )
    result = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": version_id,
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "start_time": "2026-07-06T20:00:00Z",
            "end_time": "2026-08-14T20:00:00Z",
            "data_source_mode": "imported",
        },
    )
    assert result.status_code == 201, result.text
    backtest = result.json()
    assert backtest["data_classification"] == "imported"
    assert str(first_id) in backtest["import_job_identifiers"]
    assert backtest["provider_identifiers"]


def test_backtest_uses_imported_data_and_rejects_implicit_mixing(client, engine) -> None:  # type: ignore[no-untyped-def]
    imported = client.post(
        "/api/v1/import/jobs",
        json={
            "provider_code": "synthetic",
            "symbols": ["AAPL", "SPY"],
            "mode": "full",
            "start": "2026-07-06T00:00:00Z",
            "end": "2026-08-14T23:59:59Z",
            "execute_immediately": True,
        },
    )
    assert imported.status_code == 201, imported.text
    assert imported.json()["status"] == "succeeded"
    strategies = client.get("/api/v1/strategies").json()["items"]
    version_id = next(
        item["latest_version"]["id"]
        for item in strategies
        if item["strategy_type"] == "buy_and_hold"
    )
    payload = {
        "strategy_version_id": version_id,
        "symbols": ["AAPL"],
        "benchmark_symbol": "SPY",
        "start_time": "2026-07-06T20:00:00Z",
        "end_time": "2026-08-14T20:00:00Z",
        "data_source_mode": "imported",
    }
    result = client.post("/api/v1/backtests", json=payload)
    assert result.status_code == 201, result.text
    body = result.json()
    assert body["data_classification"] == "imported"
    assert body["provider_identifiers"]
    assert imported.json()["id"] in body["import_job_identifiers"]
    assert body["adjustment_statuses"] == ["unadjusted"]

    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        imported_bar = session.scalar(
            select(PriceBar)
            .where(PriceBar.import_job_id == UUID(imported.json()["id"]))
            .order_by(PriceBar.event_time)
        )
        assert imported_bar is not None
        source = DataSource(
            name="mixed-data-test",
            provider_type="synthetic",
            is_enabled=True,
            health="healthy",
        )
        session.add(source)
        session.flush()
        session.add(
            PriceBar(
                asset_id=imported_bar.asset_id,
                interval=imported_bar.interval,
                event_time=imported_bar.event_time,
                publication_time=imported_bar.publication_time,
                effective_time=imported_bar.effective_time,
                retrieval_time=imported_bar.retrieval_time,
                open=imported_bar.open,
                high=imported_bar.high,
                low=imported_bar.low,
                close=imported_bar.close,
                adjusted_close=imported_bar.adjusted_close,
                volume=imported_bar.volume,
                data_source_id=source.id,
                provider_id=imported_bar.provider_id,
                original_symbol=imported_bar.original_symbol,
                adjustment_status=imported_bar.adjustment_status,
                checksum="f" * 64,
                is_demonstration_data=True,
            )
        )
    mixed = client.post("/api/v1/backtests", json={**payload, "data_source_mode": "auto"})
    assert mixed.status_code == 422
    assert "Mixed synthetic and imported data" in mixed.text


def test_secret_redaction_and_json_logging() -> None:
    value = redact("Authorization=Bearer-abc api_key=super-secret password=hunter2")
    assert "Bearer-abc" not in value
    assert "super-secret" not in value
    assert "hunter2" not in value
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "token=private", (), None)
    assert "private" not in JsonFormatter().format(record)


def test_single_instance_expensive_operation_rate_limit() -> None:
    limiter = InProcessRateLimiter(limit=2, window_seconds=60)
    moment = datetime(2026, 7, 29, tzinfo=UTC)
    assert limiter.allow("client:preview", now=moment) is True
    assert limiter.allow("client:preview", now=moment) is True
    assert limiter.allow("client:preview", now=moment) is False
    assert limiter.allow("client:preview", now=moment + timedelta(seconds=61)) is True


def test_worker_gracefully_stops_on_keyboard_interrupt(engine, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from packages.market_data import worker as worker_module

    monkeypatch.setattr(
        worker_module,
        "get_settings",
        lambda: Settings(database_url=str(engine.url), environment="test"),
    )
    monkeypatch.setattr(
        worker_module.time, "sleep", lambda _seconds: (_ for _ in ()).throw(KeyboardInterrupt)
    )
    assert worker_module.run(["--worker-id", "shutdown-test", "--poll-interval", "0.1"]) == 0
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        worker = session.scalar(
            select(WorkerInstance).where(WorkerInstance.worker_identifier == "shutdown-test")
        )
        assert worker is not None and worker.status == "stopped"
