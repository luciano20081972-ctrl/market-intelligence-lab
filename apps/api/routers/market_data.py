from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from apps.api.dependencies import get_db
from apps.api.schemas_sprint3 import (
    CorporateActionPage,
    CorporateActionResponse,
    ImportBatchResponse,
    ImportErrorPage,
    ImportErrorResponse,
    ImportJobCreate,
    ImportJobPage,
    ImportJobResponse,
    PageMeta,
    ProviderPage,
    ProviderResponse,
    ProviderTestRequest,
    ProviderTestResponse,
    TradingSessionPage,
    TradingSessionResponse,
)
from packages.core.config import get_settings
from packages.database.models import (
    CorporateAction,
    ExchangeCalendar,
    ImportError,
    ImportJob,
    JobEvent,
    Provider,
    TradingSession,
)
from packages.market_data.ingestion import (
    create_import_job,
    get_job,
    request_cancellation,
    restart_import_job,
    run_import_job,
)
from packages.market_data.rate_limit import InProcessRateLimiter
from packages.market_data.registry import default_registry

router = APIRouter(tags=["market-data"])
import_limiter = InProcessRateLimiter(
    limit=get_settings().expensive_request_limit_per_minute, window_seconds=60
)


def _error(code: str, message: str, status_code: int = 422) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _provider(value: Provider) -> ProviderResponse:
    return ProviderResponse(
        id=value.id,
        code=value.code,
        name=value.name,
        capabilities=value.capabilities,
        credential_environment_keys=value.credential_environment_keys,
        is_enabled=value.is_enabled,
        health=value.health,
        last_tested_at=value.last_tested_at,
        last_successful_import_at=value.last_successful_import_at,
        adapter_type=value.adapter_type,
        authentication_required=bool(value.configuration.get("authentication_required", False)),
        configuration_status="configured" if value.is_enabled else "unconfigured",
    )


def _job(value: ImportJob, *, include_batches: bool = False) -> ImportJobResponse:
    batches = []
    if include_batches:
        batches = [
            ImportBatchResponse(
                id=item.id,
                sequence=item.sequence,
                status=item.status,
                records_processed=item.records_processed,
                records_inserted=item.records_inserted,
                records_skipped=item.records_skipped,
                checksum=item.checksum,
                validation_report=item.validation_report,
            )
            for item in sorted(value.batches, key=lambda item: item.sequence)
        ]
    return ImportJobResponse(
        id=value.id,
        provider_id=value.provider_id,
        provider_code=value.provider.code,
        mode=value.mode,
        status=value.status,
        symbols=value.symbols,
        requested_at=value.requested_at,
        started_at=value.started_at,
        completed_at=value.completed_at,
        next_retry_at=value.next_retry_at,
        attempt=value.attempt,
        max_attempts=value.max_attempts,
        records_processed=value.records_processed,
        records_inserted=value.records_inserted,
        records_skipped=value.records_skipped,
        processing_duration_ms=value.processing_duration_ms,
        error_summary=value.error_summary,
        validation_report=value.validation_report,
        resume_cursor=value.resume_cursor,
        dry_run=value.dry_run,
        adjustment_preference=value.adjustment_preference,
        queue_name=value.queue_name,
        batches=batches,
    )


@router.get("/providers", response_model=ProviderPage)
def list_providers(
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    enabled: bool | None = None,
    health: str | None = None,
) -> ProviderPage:
    filters = []
    if enabled is not None:
        filters.append(Provider.is_enabled == enabled)
    if health:
        filters.append(Provider.health == health)
    total = session.scalar(select(func.count(Provider.id)).where(*filters)) or 0
    rows = session.scalars(
        select(Provider)
        .where(*filters)
        .order_by(Provider.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ProviderPage(
        items=[_provider(item) for item in rows],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )


@router.get("/providers/{provider_id}", response_model=ProviderResponse)
def provider_detail(provider_id: UUID, session: Session = Depends(get_db)) -> ProviderResponse:
    provider = session.get(Provider, provider_id)
    if provider is None:
        raise _error("provider_not_found", "Provider was not found", 404)
    return _provider(provider)


@router.post("/providers/test", response_model=ProviderTestResponse)
def test_provider(
    payload: ProviderTestRequest, session: Session = Depends(get_db)
) -> ProviderTestResponse:
    provider = session.get(Provider, payload.provider_id)
    if provider is None:
        raise _error("provider_not_found", "Provider was not found", 404)
    checked_at = datetime.now(UTC)
    details = default_registry.get(provider.code).adapter.health()
    provider.last_tested_at = checked_at
    provider.health = str(details.get("status", "unknown"))
    session.commit()
    return ProviderTestResponse(
        provider_id=provider.id, status=provider.health, checked_at=checked_at, details=details
    )


@router.post("/import/jobs", response_model=ImportJobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: ImportJobCreate,
    request: Request,
    session: Session = Depends(get_db),
) -> ImportJobResponse:
    client_key = request.client.host if request.client else "local"
    if not import_limiter.allow(f"{client_key}:import-submit"):
        raise _error("rate_limit_exceeded", "Too many import submissions", 429)
    try:
        job = create_import_job(
            session,
            provider_code=payload.provider_code,
            symbols=payload.symbols,
            mode=payload.mode,
            start=payload.start,
            end=payload.end,
            interval=payload.interval,
            max_attempts=payload.max_attempts,
            adjustment_preference=payload.adjustment_preference,
            dry_run=payload.dry_run,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        existing_event = session.scalar(
            select(JobEvent.id).where(JobEvent.job_id == job.id, JobEvent.event_type == "queued")
        )
        if existing_event is None:
            session.add(
                JobEvent(
                    job_id=job.id,
                    event_type="queued",
                    to_status="queued",
                    message="Import job accepted",
                    details={"provider_code": payload.provider_code},
                )
            )
        if payload.execute_immediately:
            run_import_job(session, job)
        session.commit()
        job = get_job(session, job.id)
        return _job(job, include_batches=True)
    except ValueError as exc:
        session.rollback()
        raise _error("invalid_import_request", str(exc)) from exc


@router.get("/import/jobs", response_model=ImportJobPage)
def list_jobs(
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    job_status: str | None = Query(default=None, alias="status"),
    provider_id: UUID | None = None,
) -> ImportJobPage:
    filters = []
    if job_status:
        filters.append(ImportJob.status == job_status)
    if provider_id:
        filters.append(ImportJob.provider_id == provider_id)
    total = session.scalar(select(func.count(ImportJob.id)).where(*filters)) or 0
    rows = session.scalars(
        select(ImportJob)
        .options(selectinload(ImportJob.provider))
        .where(*filters)
        .order_by(ImportJob.requested_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ImportJobPage(
        items=[_job(item) for item in rows],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )


@router.get("/import/jobs/{job_id}", response_model=ImportJobResponse)
def job_detail(job_id: UUID, session: Session = Depends(get_db)) -> ImportJobResponse:
    job = session.scalar(
        select(ImportJob)
        .options(selectinload(ImportJob.provider), selectinload(ImportJob.batches))
        .where(ImportJob.id == job_id)
    )
    if job is None:
        raise _error("import_job_not_found", "Import job was not found", 404)
    return _job(job, include_batches=True)


@router.post("/import/jobs/{job_id}/cancel", response_model=ImportJobResponse)
def cancel_job(job_id: UUID, session: Session = Depends(get_db)) -> ImportJobResponse:
    try:
        job = request_cancellation(session, get_job(session, job_id))
        session.commit()
        return _job(job)
    except ValueError as exc:
        session.rollback()
        code = 404 if "not found" in str(exc) else 409
        raise _error("import_job_not_cancellable", str(exc), code) from exc


@router.post("/import/jobs/{job_id}/restart", response_model=ImportJobResponse)
def restart_job(job_id: UUID, session: Session = Depends(get_db)) -> ImportJobResponse:
    try:
        job = restart_import_job(session, get_job(session, job_id))
        run_import_job(session, job)
        session.commit()
        return _job(job, include_batches=True)
    except ValueError as exc:
        session.rollback()
        code = 404 if "not found" in str(exc) else 409
        raise _error("import_job_not_restartable", str(exc), code) from exc


@router.get("/import/history", response_model=ImportJobPage)
def import_history(
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> ImportJobPage:
    filters = [ImportJob.status.in_(["succeeded", "failed", "cancelled"])]
    total = session.scalar(select(func.count(ImportJob.id)).where(*filters)) or 0
    rows = session.scalars(
        select(ImportJob)
        .options(selectinload(ImportJob.provider))
        .where(*filters)
        .order_by(ImportJob.requested_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ImportJobPage(
        items=[_job(item) for item in rows],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )


@router.get("/import/errors", response_model=ImportErrorPage)
def import_errors(
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    job_id: UUID | None = None,
    retryable: bool | None = None,
) -> ImportErrorPage:
    filters = []
    if job_id:
        filters.append(ImportError.job_id == job_id)
    if retryable is not None:
        filters.append(ImportError.is_retryable == retryable)
    total = session.scalar(select(func.count(ImportError.id)).where(*filters)) or 0
    rows = session.scalars(
        select(ImportError)
        .where(*filters)
        .order_by(ImportError.occurred_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ImportErrorPage(
        items=[
            ImportErrorResponse(
                id=item.id,
                job_id=item.job_id,
                batch_id=item.batch_id,
                error_code=item.error_code,
                message=item.message,
                record_identifier=item.record_identifier,
                is_retryable=item.is_retryable,
                occurred_at=item.occurred_at,
            )
            for item in rows
        ],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )


@router.get("/corporate-actions", response_model=CorporateActionPage)
def corporate_actions(
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    symbol: str | None = None,
    action_type: str | None = None,
) -> CorporateActionPage:
    filters = []
    if symbol:
        filters.append(CorporateAction.original_symbol == symbol.upper())
    if action_type:
        filters.append(CorporateAction.action_type == action_type)
    total = session.scalar(select(func.count(CorporateAction.id)).where(*filters)) or 0
    rows = session.scalars(
        select(CorporateAction)
        .options(selectinload(CorporateAction.asset))
        .where(*filters)
        .order_by(CorporateAction.effective_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    provider_codes = {item.id: item.code for item in session.scalars(select(Provider)).all()}
    return CorporateActionPage(
        items=[
            CorporateActionResponse(
                id=item.id,
                symbol=item.original_symbol,
                provider_code=provider_codes.get(item.provider_id, "unknown"),
                action_type=item.action_type,
                effective_time=item.effective_time,
                publication_time=item.publication_time,
                ratio=str(item.ratio) if item.ratio is not None else None,
                amount=str(item.amount) if item.amount is not None else None,
                currency=item.currency,
                old_symbol=item.old_symbol,
                new_symbol=item.new_symbol,
                adjustment_status=item.action_type,
            )
            for item in rows
        ],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )


@router.get("/exchange-calendar", response_model=TradingSessionPage)
def exchange_calendar(
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=31, ge=1, le=366),
    calendar_code: str = "XNYS",
    start_date: str | None = None,
    end_date: str | None = None,
) -> TradingSessionPage:
    filters = [ExchangeCalendar.code == calendar_code.upper()]
    if start_date:
        filters.append(TradingSession.session_date >= start_date)
    if end_date:
        filters.append(TradingSession.session_date <= end_date)
    base = select(TradingSession).join(ExchangeCalendar).where(*filters)
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.scalars(
        base.options(selectinload(TradingSession.calendar))
        .order_by(TradingSession.session_date)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return TradingSessionPage(
        items=[
            TradingSessionResponse(
                id=item.id,
                calendar_code=item.calendar.code,
                timezone=item.calendar.timezone,
                session_date=item.session_date,
                open_time=item.open_time,
                close_time=item.close_time,
                is_early_close=item.is_early_close,
                status=item.status,
            )
            for item in rows
        ],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )
