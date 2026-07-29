from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.database.models import ImportError, PriceBar, Provider
from packages.market_data.adapters import SyntheticHistoricalAdapter
from packages.market_data.calendars import is_open_session, session_times
from packages.market_data.corporate_actions import adjusted_close_for, validate_corporate_action
from packages.market_data.ingestion import (
    create_import_job,
    restart_import_job,
    retry_delay_seconds,
    run_import_job,
)
from packages.market_data.quality import validate_historical_bars
from packages.market_data.registry import ProviderRegistry, default_registry
from packages.market_data.types import (
    CorporateActionRecord,
    HistoricalBarRecord,
    ProviderTemporaryError,
)


def _bar(**overrides: object) -> HistoricalBarRecord:
    values: dict[str, object] = {
        "symbol": "AAPL",
        "interval": "1d",
        "event_time": datetime(2026, 7, 6, 20, tzinfo=UTC),
        "publication_time": datetime(2026, 7, 6, 20, 1, tzinfo=UTC),
        "effective_time": datetime(2026, 7, 6, 20, tzinfo=UTC),
        "retrieval_time": datetime(2026, 7, 6, 20, 2, tzinfo=UTC),
        "open": Decimal("100"),
        "high": Decimal("102"),
        "low": Decimal("99"),
        "close": Decimal("101"),
        "adjusted_close": Decimal("101"),
        "volume": 100,
    }
    values.update(overrides)
    return HistoricalBarRecord(**values)  # type: ignore[arg-type]


def _job(session: Session, symbols: list[str] | None = None):  # type: ignore[no-untyped-def]
    return create_import_job(
        session,
        provider_code="synthetic",
        symbols=symbols or ["AAPL"],
        mode="incremental",
        start=datetime(2026, 7, 6, tzinfo=UTC),
        end=datetime(2026, 7, 10, 23, 59, tzinfo=UTC),
    )


def test_provider_registry_contains_disabled_placeholders() -> None:
    codes = {item.code: item for item in default_registry.all()}
    assert codes["synthetic"].enabled_by_default is True
    for code in {
        "alpha_vantage",
        "twelve_data",
        "polygon",
        "financial_modeling_prep",
        "tiingo",
        "stooq",
        "yahoo_finance",
    }:
        assert codes[code].enabled_by_default is False
    registry = ProviderRegistry()
    registry.register(SyntheticHistoricalAdapter())
    try:
        registry.register(SyntheticHistoricalAdapter())
    except ValueError as exc:
        assert "already registered" in str(exc)


def test_validation_detects_duplicate_and_invalid_values() -> None:
    invalid = _bar(high=Decimal("98"), low=Decimal("103"), volume=-1)
    report = validate_historical_bars(
        [invalid, invalid],
        valid_session_dates={"2026-07-06"},
        now=datetime(2026, 7, 20, tzinfo=UTC),
    )
    codes = {issue.code for issue in report.issues}
    assert {"impossible_ohlc", "negative_volume", "duplicate_bar", "stale_import"} <= codes
    assert report.is_valid is False


def test_retry_logic_uses_exponential_backoff(engine) -> None:  # type: ignore[no-untyped-def]
    class FlakyAdapter(SyntheticHistoricalAdapter):
        calls = 0

        def fetch_historical_bars(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.calls += 1
            if self.calls == 1:
                raise ProviderTemporaryError("rate limited")
            return super().fetch_historical_bars(*args, **kwargs)

    registry = ProviderRegistry()
    registry.register(FlakyAdapter(), enabled_by_default=True)
    with Session(engine) as session:
        job = _job(session)
        run_import_job(session, job, registry)
        assert job.status == "retrying"
        assert job.next_retry_at is not None
        run_import_job(session, job, registry)
        assert job.status == "succeeded"
        assert job.attempt == 2
        assert retry_delay_seconds(1) == 30
        assert retry_delay_seconds(3) == 120


def test_duplicate_prevention_and_provenance(engine) -> None:  # type: ignore[no-untyped-def]
    with Session(engine) as session:
        first = _job(session)
        run_import_job(session, first)
        session.commit()
        second = _job(session)
        run_import_job(session, second)
        session.commit()
        assert first.records_inserted > 0
        assert second.records_inserted == 0
        assert second.records_skipped == second.records_processed
        provider = session.scalar(select(Provider).where(Provider.code == "synthetic"))
        bar = session.scalar(
            select(PriceBar)
            .where(PriceBar.provider_id == provider.id)
            .order_by(PriceBar.event_time.desc())
        )
        assert bar is not None
        assert bar.original_symbol == "AAPL"
        assert bar.checksum and bar.record_version == 1
        assert bar.retrieval_time.tzinfo is not None
        assert bar.publication_time.tzinfo is not None
        assert bar.effective_time.tzinfo is not None


def test_restart_after_validation_failure(engine) -> None:  # type: ignore[no-untyped-def]
    class InvalidAdapter(SyntheticHistoricalAdapter):
        def fetch_historical_bars(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return [_bar(volume=-1)]

    bad = ProviderRegistry()
    bad.register(InvalidAdapter(), enabled_by_default=True)
    good = ProviderRegistry()
    good.register(SyntheticHistoricalAdapter(), enabled_by_default=True)
    with Session(engine) as session:
        job = _job(session)
        run_import_job(session, job, bad)
        assert job.status == "failed"
        assert session.scalar(
            select(func.count(ImportError.id)).where(ImportError.job_id == job.id)
        )
        restart_import_job(session, job)
        run_import_job(session, job, good)
        assert job.status == "succeeded"


def test_corporate_action_validation_and_adjusted_price() -> None:
    split = CorporateActionRecord(
        symbol="AAPL",
        action_type="split",
        ratio=Decimal("2"),
        effective_time=datetime(2026, 7, 7, tzinfo=UTC),
        publication_time=datetime(2026, 7, 1, tzinfo=UTC),
        retrieval_time=datetime(2026, 7, 1, 1, tzinfo=UTC),
    )
    validate_corporate_action(split)
    assert adjusted_close_for(_bar(), [split]) == Decimal("50.5")
    dividend = CorporateActionRecord(
        symbol="AAPL",
        action_type="dividend",
        amount=Decimal("1"),
        currency="USD",
        effective_time=datetime(2026, 7, 7, tzinfo=UTC),
        publication_time=datetime(2026, 7, 1, tzinfo=UTC),
        retrieval_time=datetime(2026, 7, 1, 1, tzinfo=UTC),
    )
    assert adjusted_close_for(_bar(), [dividend]) == Decimal("100")


def test_exchange_calendar_weekends_holidays_early_close_and_timezone(engine) -> None:  # type: ignore[no-untyped-def]
    from packages.database.models import ExchangeCalendar

    with Session(engine) as session:
        calendar = session.scalar(select(ExchangeCalendar).where(ExchangeCalendar.code == "XNYS"))
        assert calendar is not None
        assert is_open_session(calendar, date(2026, 7, 4)) is False
        assert is_open_session(calendar, date(2026, 7, 3)) is False
    opening, closing = session_times(date(2026, 11, 27), "America/New_York", early_close=True)
    assert opening.tzinfo is not None and closing.tzinfo is not None
    assert (closing - opening).total_seconds() == 3.5 * 3600


def test_closed_session_bars_are_rejected(engine) -> None:  # type: ignore[no-untyped-def]
    with Session(engine) as session:
        job = create_import_job(
            session,
            provider_code="synthetic",
            symbols=["AAPL"],
            mode="full",
            start=datetime(2026, 7, 2, tzinfo=UTC),
            end=datetime(2026, 7, 4, 23, 59, tzinfo=UTC),
        )
        run_import_job(session, job)
        assert job.status == "failed"
        assert any(item.error_code == "missing_session" for item in job.errors)


def test_market_data_api_workflow(client) -> None:  # type: ignore[no-untyped-def]
    providers = client.get("/api/v1/providers?page_size=100")
    assert providers.status_code == 200
    synthetic = next(item for item in providers.json()["items"] if item["code"] == "synthetic")
    health = client.post("/api/v1/providers/test", json={"provider_id": synthetic["id"]})
    assert health.status_code == 200 and health.json()["status"] == "healthy"
    created = client.post(
        "/api/v1/import/jobs",
        json={
            "provider_code": "synthetic",
            "symbols": ["NVDA"],
            "mode": "incremental",
            "start": "2026-07-06T00:00:00Z",
            "end": "2026-07-10T23:59:59Z",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "succeeded" and body["records_inserted"] > 0
    assert client.get(f"/api/v1/import/jobs/{body['id']}").status_code == 200
    assert client.get("/api/v1/import/history").json()["meta"]["total"] >= 1
    assert client.get("/api/v1/import/errors").status_code == 200
    assert client.get("/api/v1/corporate-actions").status_code == 200
    calendar = client.get("/api/v1/exchange-calendar?start_date=2026-07-01&end_date=2026-07-10")
    assert calendar.status_code == 200 and calendar.json()["meta"]["total"] > 0


def test_disabled_provider_import_is_rejected(client) -> None:  # type: ignore[no-untyped-def]
    response = client.post(
        "/api/v1/import/jobs",
        json={
            "provider_code": "polygon",
            "symbols": ["AAPL"],
            "mode": "full",
            "start": "2026-07-06T00:00:00Z",
            "end": "2026-07-10T23:59:59Z",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_import_request"
