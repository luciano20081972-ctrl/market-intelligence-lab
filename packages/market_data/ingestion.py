from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.database.models import (
    Asset,
    AssetMetadataVersion,
    CorporateAction,
    DataSource,
    ImportBatch,
    ImportError,
    ImportJob,
    JobEvent,
    PriceBar,
    Provider,
    ProviderRateLimitState,
    ProviderSymbolMapping,
    TradingSession,
)
from packages.market_data.corporate_actions import validate_corporate_action
from packages.market_data.quality import ValidationReport, validate_historical_bars, validate_symbol
from packages.market_data.registry import ProviderRegistry, default_registry
from packages.market_data.types import (
    HistoricalBarRecord,
    ProviderError,
    ProviderRateLimitError,
    ProviderTemporaryError,
)

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "dead_letter"}
RESTARTABLE_STATUSES = {"failed", "retrying", "interrupted", "cancelled"}


def _checksum(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def retry_delay_seconds(attempt: int, base_seconds: int = 30, cap_seconds: int = 3600) -> int:
    if attempt < 1:
        raise ValueError("attempt must be at least 1")
    return min(cap_seconds, base_seconds * (2 ** (attempt - 1)))


def create_import_job(
    session: Session,
    *,
    provider_code: str,
    symbols: list[str],
    mode: str,
    start: datetime,
    end: datetime,
    interval: str = "1d",
    max_attempts: int = 3,
    adjustment_preference: str = "unadjusted",
    dry_run: bool = False,
    idempotency_key: str | None = None,
    queue_name: str = "manual",
    workspace_id: UUID | None = None,
) -> ImportJob:
    provider = session.scalar(select(Provider).where(Provider.code == provider_code.lower()))
    if provider is None:
        raise ValueError(f"unknown provider '{provider_code}'")
    if not provider.is_enabled:
        raise ValueError(f"provider '{provider.code}' is disabled")
    normalized = sorted({symbol.strip().upper() for symbol in symbols})
    invalid = [symbol for symbol in normalized if not validate_symbol(symbol)]
    if invalid:
        raise ValueError(f"invalid symbols: {', '.join(invalid)}")
    if mode not in {"full", "incremental"}:
        raise ValueError("mode must be 'full' or 'incremental'")
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError("start and end must be timezone-aware and start must precede end")
    if max_attempts < 1 or max_attempts > 10:
        raise ValueError("max_attempts must be between 1 and 10")
    if adjustment_preference not in {"adjusted", "unadjusted", "provider_default"}:
        raise ValueError("invalid adjustment preference")
    if idempotency_key:
        existing = session.scalar(
            select(ImportJob).where(ImportJob.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing
    job = ImportJob(
        workspace_id=workspace_id or session.info.get("workspace_id"),
        provider_id=provider.id,
        mode=mode,
        status="queued",
        symbols=normalized,
        request_configuration={
            "start": start.isoformat(),
            "end": end.isoformat(),
            "interval": interval,
            "adjustment_preference": adjustment_preference,
            "dry_run": dry_run,
        },
        max_attempts=max_attempts,
        adjustment_preference=adjustment_preference,
        dry_run=dry_run,
        idempotency_key=idempotency_key,
        queue_name=queue_name,
    )
    session.add(job)
    session.flush()
    return job


def request_cancellation(session: Session, job: ImportJob) -> ImportJob:
    if job.status in TERMINAL_STATUSES:
        raise ValueError(f"cannot cancel a {job.status} job")
    previous = job.status
    job.cancel_requested = True
    if job.status == "queued":
        job.status = "cancelled"
        job.completed_at = datetime.now(UTC)
    session.add(
        JobEvent(
            job_id=job.id,
            event_type="cancellation_requested",
            from_status=previous,
            to_status=job.status,
            message="Cancellation requested",
        )
    )
    session.flush()
    return job


def restart_import_job(session: Session, job: ImportJob) -> ImportJob:
    if job.status not in RESTARTABLE_STATUSES:
        raise ValueError(f"job status '{job.status}' is not restartable")
    job.status = "queued"
    job.cancel_requested = False
    job.completed_at = None
    job.next_retry_at = None
    job.error_summary = None
    session.flush()
    return job


def _data_source(session: Session, provider: Provider) -> DataSource:
    name = f"provider:{provider.code}"
    source = session.scalar(select(DataSource).where(DataSource.name == name))
    if source is None:
        source = DataSource(
            name=name,
            provider_type="historical-market-data",
            is_enabled=True,
            health="healthy",
            license_notes=(
                "Provider terms and redistribution rights must be reviewed before production use."
            ),
        )
        session.add(source)
        session.flush()
    return source


def _asset(session: Session, provider: Provider, adapter: Any, symbol: str) -> Asset:
    asset = session.scalar(select(Asset).where(Asset.symbol == symbol))
    metadata = adapter.fetch_asset_metadata(symbol)
    if asset is None:
        asset = Asset(
            symbol=symbol,
            name=metadata.name,
            asset_type=metadata.asset_type,
            exchange=metadata.exchange,
            currency=metadata.currency,
            sector=metadata.sector,
            industry=metadata.industry,
        )
        session.add(asset)
        session.flush()
    checksum = metadata.checksum or _checksum(metadata.__dict__)
    exists = session.scalar(
        select(AssetMetadataVersion.id).where(
            AssetMetadataVersion.asset_id == asset.id,
            AssetMetadataVersion.provider_id == provider.id,
            AssetMetadataVersion.version == metadata.version,
        )
    )
    if exists is None:
        session.add(
            AssetMetadataVersion(
                asset_id=asset.id,
                provider_id=provider.id,
                original_symbol=metadata.symbol,
                metadata_json={"name": metadata.name, **metadata.metadata},
                effective_time=metadata.effective_time,
                retrieval_time=metadata.retrieval_time,
                checksum=checksum,
                version=metadata.version,
            )
        )
    provider_symbol = str(metadata.metadata.get("provider_symbol", metadata.symbol))
    mapping = session.scalar(
        select(ProviderSymbolMapping).where(
            ProviderSymbolMapping.provider_id == provider.id,
            ProviderSymbolMapping.canonical_symbol == asset.symbol,
        )
    )
    if mapping is None:
        session.add(
            ProviderSymbolMapping(
                provider_id=provider.id,
                canonical_symbol=asset.symbol,
                provider_symbol=provider_symbol,
                exchange_code=asset.exchange,
                metadata_json={"source": "adapter_metadata"},
            )
        )
    return asset


def _valid_session_dates(session: Session, start: datetime, end: datetime) -> set[str]:
    rows = session.scalars(
        select(TradingSession.session_date).where(
            TradingSession.open_time >= start,
            TradingSession.open_time <= end,
            TradingSession.status == "open",
        )
    ).all()
    return set(rows)


def _record_checksum(record: HistoricalBarRecord) -> str:
    return record.checksum or _checksum(record.__dict__)


def _persist_actions(
    session: Session,
    provider: Provider,
    adapter: Any,
    asset: Asset,
    symbol: str,
    start: datetime,
    end: datetime,
) -> None:
    for record in adapter.fetch_corporate_actions(symbol, start, end):
        validate_corporate_action(record)
        checksum = record.checksum or _checksum(record.__dict__)
        exists = session.scalar(
            select(CorporateAction.id).where(
                CorporateAction.provider_id == provider.id,
                CorporateAction.checksum == checksum,
            )
        )
        if exists is None:
            session.add(
                CorporateAction(
                    asset_id=asset.id,
                    provider_id=provider.id,
                    action_type=record.action_type,
                    original_symbol=record.symbol,
                    effective_time=record.effective_time,
                    publication_time=record.publication_time,
                    retrieval_time=record.retrieval_time,
                    ratio=record.ratio,
                    amount=record.amount,
                    currency=record.currency,
                    old_symbol=record.old_symbol,
                    new_symbol=record.new_symbol,
                    checksum=checksum,
                    record_version=record.version,
                )
            )


def _issue_dict(report: ValidationReport) -> dict[str, Any]:
    return {
        "valid": report.is_valid,
        "issues": [issue.__dict__ for issue in report.issues],
        "error_count": sum(issue.severity == "error" for issue in report.issues),
        "warning_count": sum(issue.severity == "warning" for issue in report.issues),
    }


def run_import_job(
    session: Session,
    job: ImportJob,
    registry: ProviderRegistry = default_registry,
    heartbeat: Callable[[], None] | None = None,
) -> ImportJob:
    if job.status not in {"queued", "retrying", "interrupted", "running"}:
        raise ValueError(f"job status '{job.status}' cannot be run")
    provider = session.get(Provider, job.provider_id)
    if provider is None or not provider.is_enabled:
        raise ValueError("job provider is unavailable or disabled")
    registered = registry.get(provider.code)
    adapter = registered.adapter
    config = job.request_configuration
    start = datetime.fromisoformat(str(config["start"])).astimezone(UTC)
    end = datetime.fromisoformat(str(config["end"])).astimezone(UTC)
    interval = str(config.get("interval", "1d"))
    valid_sessions = _valid_session_dates(session, start, end)
    source = _data_source(session, provider)
    began = time.perf_counter()
    job.status = "running"
    job.started_at = job.started_at or datetime.now(UTC)
    job.attempt += 1
    session.flush()
    start_index = int(job.resume_cursor.get("symbol_index", 0))
    reports: list[dict[str, Any]] = list(job.validation_report.get("batches", []))
    try:
        for sequence, symbol in enumerate(job.symbols):
            if heartbeat:
                heartbeat()
            if sequence < start_index:
                continue
            if job.cancel_requested:
                job.status = "cancelled"
                break
            batch = session.scalar(
                select(ImportBatch).where(
                    ImportBatch.job_id == job.id, ImportBatch.sequence == sequence
                )
            )
            if batch is None:
                batch = ImportBatch(
                    job_id=job.id,
                    sequence=sequence,
                    status="running",
                    request_timestamp=datetime.now(UTC),
                    checksum="",
                )
                session.add(batch)
                session.flush()
            else:
                batch.status = "running"
            asset = _asset(session, provider, adapter, symbol)
            fetch_start = start
            if job.mode == "incremental":
                latest = session.scalar(
                    select(PriceBar.event_time)
                    .where(
                        PriceBar.asset_id == asset.id,
                        PriceBar.interval == interval,
                        PriceBar.data_source_id == source.id,
                    )
                    .order_by(PriceBar.event_time.desc())
                    .limit(1)
                )
                if latest is not None:
                    fetch_start = max(start, latest + timedelta(microseconds=1))
            records = (
                adapter.fetch_historical_bars(symbol, fetch_start, end, interval)
                if fetch_start < end
                else []
            )
            if job.adjustment_preference == "adjusted" and any(
                record.adjustment_status not in {"adjusted", "split_adjusted", "total_return"}
                for record in records
            ):
                raise ValueError(
                    f"provider '{provider.code}' cannot satisfy the requested adjusted series"
                )
            report = validate_historical_bars(
                records,
                valid_session_dates=valid_sessions or None,
                stale_after_days=7,
                now=end + timedelta(days=7),
            )
            report_data = _issue_dict(report)
            batch.validation_report = report_data
            batch.records_processed = len(records)
            job.records_processed += len(records)
            if not report.is_valid:
                for issue in report.issues:
                    if issue.severity == "error":
                        session.add(
                            ImportError(
                                job_id=job.id,
                                batch_id=batch.id,
                                error_code=issue.code,
                                message=issue.message,
                                record_identifier=issue.record_identifier,
                                payload_summary={"symbol": symbol},
                                is_retryable=False,
                            )
                        )
                batch.status = "failed_validation"
                batch.completed_at = datetime.now(UTC)
                reports.append({"symbol": symbol, **report_data})
                job.error_summary = f"validation failed for {symbol}"
                job.status = "failed"
                break
            checksums: list[str] = []
            for record in records:
                checksum = _record_checksum(record)
                checksums.append(checksum)
                duplicate = session.scalar(
                    select(PriceBar).where(
                        PriceBar.asset_id == asset.id,
                        PriceBar.interval == record.interval,
                        PriceBar.event_time == record.event_time,
                        PriceBar.data_source_id == source.id,
                    )
                )
                checksum_duplicate = session.scalar(
                    select(PriceBar.id).where(
                        PriceBar.provider_id == provider.id,
                        PriceBar.checksum == checksum,
                    )
                )
                if duplicate is not None:
                    if duplicate.checksum and duplicate.checksum != checksum:
                        session.add(
                            ImportError(
                                job_id=job.id,
                                batch_id=batch.id,
                                error_code="conflicting_reimport",
                                message=(
                                    "Incoming provider record conflicts with the preserved "
                                    "canonical record"
                                ),
                                record_identifier=(
                                    f"{record.symbol}:{record.interval}:{record.event_time.isoformat()}"
                                ),
                                payload_summary={
                                    "existing_checksum": duplicate.checksum,
                                    "incoming_checksum": checksum,
                                    "resolution": "preserved_existing",
                                },
                                is_retryable=False,
                            )
                        )
                    batch.records_skipped += 1
                    job.records_skipped += 1
                    continue
                if checksum_duplicate is not None:
                    batch.records_skipped += 1
                    job.records_skipped += 1
                    continue
                if job.dry_run:
                    batch.records_skipped += 1
                    job.records_skipped += 1
                    continue
                session.add(
                    PriceBar(
                        asset_id=asset.id,
                        interval=record.interval,
                        event_time=record.event_time,
                        publication_time=record.publication_time,
                        effective_time=record.effective_time,
                        retrieval_time=record.retrieval_time,
                        open=record.open,
                        high=record.high,
                        low=record.low,
                        close=record.close,
                        adjusted_close=record.adjusted_close,
                        volume=record.volume,
                        data_source_id=source.id,
                        provider_id=provider.id,
                        original_symbol=record.symbol,
                        adjustment_status=record.adjustment_status,
                        checksum=checksum,
                        record_version=record.version,
                        import_job_id=job.id,
                        raw_provider_metadata=record.raw_metadata or {},
                    )
                )
                batch.records_inserted += 1
                job.records_inserted += 1
            _persist_actions(session, provider, adapter, asset, symbol, start, end)
            batch.checksum = _checksum({"symbol": symbol, "checksums": checksums})
            batch.retrieval_timestamp = max(
                (item.retrieval_time for item in records), default=datetime.now(UTC)
            )
            batch.publication_timestamp = max(
                (item.publication_time for item in records), default=None
            )
            batch.effective_timestamp = max((item.effective_time for item in records), default=None)
            batch.status = "succeeded"
            batch.completed_at = datetime.now(UTC)
            reports.append({"symbol": symbol, **report_data})
            job.resume_cursor = {"symbol_index": sequence + 1}
            session.flush()
            if heartbeat:
                heartbeat()
        if job.status == "running":
            job.status = "succeeded"
            provider.last_successful_import_at = datetime.now(UTC)
            source.last_successful_retrieval = provider.last_successful_import_at
        if job.status in TERMINAL_STATUSES:
            job.completed_at = datetime.now(UTC)
    except ProviderTemporaryError as exc:
        if isinstance(exc, ProviderRateLimitError):
            rate_state = session.scalar(
                select(ProviderRateLimitState).where(
                    ProviderRateLimitState.provider_id == provider.id
                )
            )
            if rate_state is None:
                rate_state = ProviderRateLimitState(provider_id=provider.id)
                session.add(rate_state)
            rate_state.rate_limit_events += 1
            rate_state.last_response_status = 429
            rate_state.updated_at = datetime.now(UTC)
        session.add(
            ImportError(
                job_id=job.id,
                error_code=exc.classification,
                message=str(exc),
                payload_summary={
                    "attempt": job.attempt,
                    "provider_classification": exc.classification,
                },
                is_retryable=True,
            )
        )
        job.error_summary = str(exc)
        if job.attempt < job.max_attempts:
            job.status = "retrying"
            job.next_retry_at = datetime.now(UTC) + timedelta(
                seconds=retry_delay_seconds(job.attempt)
            )
        else:
            job.status = "failed"
            job.completed_at = datetime.now(UTC)
    except ProviderError as exc:
        session.add(
            ImportError(
                job_id=job.id,
                error_code=exc.classification,
                message=str(exc),
                payload_summary={
                    "attempt": job.attempt,
                    "provider_classification": exc.classification,
                },
                is_retryable=False,
            )
        )
        job.status = "failed"
        job.error_summary = str(exc)
        job.completed_at = datetime.now(UTC)
    except (ValueError, IntegrityError) as exc:
        session.add(
            ImportError(
                job_id=job.id,
                error_code="import_error",
                message=str(exc),
                payload_summary={"attempt": job.attempt},
                is_retryable=False,
            )
        )
        job.status = "failed"
        job.error_summary = str(exc)
        job.completed_at = datetime.now(UTC)
    finally:
        job.validation_report = {"batches": reports}
        job.processing_duration_ms += int((time.perf_counter() - began) * 1000)
        session.flush()
    return job


def get_job(session: Session, job_id: UUID) -> ImportJob:
    job = session.get(ImportJob, job_id)
    if job is None:
        raise ValueError("import job was not found")
    return job
