from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from apps.api.schemas_sprint4 import (
    ImportPreviewRequest,
    ReconciliationRequest,
    ScheduleCreate,
    ScheduleUpdate,
)
from packages.core.config import get_settings
from packages.database.models import (
    ImportSchedule,
    JobEvent,
    Provider,
    ProviderHealthSnapshot,
    ProviderRateLimitState,
    ReconciliationIssue,
    ReconciliationRun,
    ScheduleRun,
    WorkerInstance,
)
from packages.market_data.ingestion import get_job, restart_import_job
from packages.market_data.operations import (
    process_due_schedules,
    queue_summary,
    recover_abandoned_jobs,
)
from packages.market_data.quality import validate_historical_bars
from packages.market_data.rate_limit import InProcessRateLimiter
from packages.market_data.reconciliation import preview_reconciliation, run_reconciliation
from packages.market_data.registry import default_registry
from packages.market_data.types import ProviderError

router = APIRouter(tags=["operations"])
limiter = InProcessRateLimiter(
    limit=get_settings().expensive_request_limit_per_minute, window_seconds=60
)


def _error(code: str, message: str, status_code: int = 422) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _guard(request: Request) -> None:
    client = request.client.host if request.client else "local"
    if not limiter.allow(f"{client}:{request.url.path}"):
        raise _error("rate_limit_exceeded", "Too many expensive operations", 429)


def _schedule(value: ImportSchedule) -> dict[str, Any]:
    return {
        "id": value.id,
        "provider_id": value.provider_id,
        "name": value.name,
        "symbols": value.symbols,
        "mode": value.mode,
        "adjustment_preference": value.adjustment_preference,
        "timezone": value.timezone,
        "is_enabled": value.is_enabled,
        "next_run_at": value.next_run_at,
        "last_run_at": value.last_run_at,
        "failure_count": value.failure_count,
        "last_error": value.last_error,
        "date_range_policy": value.date_range_policy,
    }


@router.post("/providers/{provider_id}/test")
def test_provider_connection(
    provider_id: UUID, request: Request, session: Session = Depends(get_db)
) -> dict[str, Any]:
    _guard(request)
    provider = session.get(Provider, provider_id)
    if provider is None:
        raise _error("provider_not_found", "Provider was not found", 404)
    adapter = default_registry.get(provider.code).adapter
    checked = datetime.now(UTC)
    try:
        test_method = getattr(adapter, "test_connectivity", None)
        result = test_method() if test_method else adapter.health()
        connectivity = str(result.get("connectivity", result.get("status", "unknown")))
        provider.health = "healthy" if connectivity in {"connected", "healthy"} else "degraded"
        message = "Provider connection test completed"
    except (ProviderError, ValueError) as exc:
        result = {"status": "unavailable", "connectivity": "unavailable"}
        provider.health = "unavailable"
        connectivity = "unavailable"
        message = str(exc)
    provider.last_tested_at = checked
    session.add(
        ProviderHealthSnapshot(
            provider_id=provider.id,
            status=provider.health,
            configured=provider.is_enabled,
            connectivity_status=connectivity,
            message=message,
            details=result,
        )
    )
    session.commit()
    return {"provider_id": provider.id, "checked_at": checked, **result}


@router.get("/providers/{provider_id}/status")
def provider_status(provider_id: UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    provider = session.get(Provider, provider_id)
    if provider is None:
        raise _error("provider_not_found", "Provider was not found", 404)
    latest = session.scalar(
        select(ProviderHealthSnapshot)
        .where(ProviderHealthSnapshot.provider_id == provider.id)
        .order_by(ProviderHealthSnapshot.checked_at.desc())
    )
    quota = session.scalar(
        select(ProviderRateLimitState).where(ProviderRateLimitState.provider_id == provider.id)
    )
    return {
        "provider_id": provider.id,
        "code": provider.code,
        "configured": provider.is_enabled,
        "health": provider.health,
        "connectivity": latest.connectivity_status if latest else "not_tested",
        "last_checked_at": latest.checked_at if latest else None,
        "last_successful_import_at": provider.last_successful_import_at,
        "stale": provider.last_successful_import_at is None
        or datetime.now(UTC) - provider.last_successful_import_at > timedelta(days=7),
        "authentication_required": bool(
            provider.configuration.get("authentication_required", False)
        ),
        "rate_limit": {
            "requests_remaining": quota.requests_remaining if quota else None,
            "reset_at": quota.reset_at if quota else None,
            "events": quota.rate_limit_events if quota else 0,
        },
    }


@router.post("/import/jobs/preview")
def preview_import(
    payload: ImportPreviewRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    _guard(request)
    provider = session.scalar(select(Provider).where(Provider.code == payload.provider_code))
    if provider is None or not provider.is_enabled:
        raise _error("provider_unavailable", "Provider is unknown or disabled")
    adapter = default_registry.get(provider.code).adapter
    reports = []
    for symbol in payload.symbols:
        try:
            records = adapter.fetch_historical_bars(symbol, payload.start, payload.end, "1d")
            report = validate_historical_bars(records, now=payload.end + timedelta(days=7))
            reports.append(
                {
                    "symbol": symbol,
                    "provider_symbol": getattr(adapter, "normalize_symbol", lambda item: item)(
                        symbol
                    ),
                    "records": len(records),
                    "valid": report.is_valid,
                    "issues": report.as_dict()["issues"],
                }
            )
        except (ProviderError, ValueError) as exc:
            reports.append({"symbol": symbol, "records": 0, "valid": False, "error": str(exc)})
    return {
        "provider": provider.code,
        "mode": payload.mode,
        "dry_run": True,
        "adjustment_preference": payload.adjustment_preference,
        "reports": reports,
        "can_submit": all(item["valid"] for item in reports),
    }


@router.post("/import/jobs/{job_id}/retry")
def retry_job(job_id: UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        job = get_job(session, job_id)
        previous = job.status
        job = restart_import_job(session, job)
        session.add(
            JobEvent(
                job_id=job.id,
                event_type="manual_retry",
                from_status=previous,
                to_status="queued",
                message="Manual retry requested",
            )
        )
        session.commit()
        return {"id": job.id, "status": job.status}
    except ValueError as exc:
        session.rollback()
        raise _error("job_not_retryable", str(exc), 409) from exc


@router.get("/import/jobs/{job_id}/events")
def job_events(job_id: UUID, session: Session = Depends(get_db)) -> list[dict[str, Any]]:
    get_job(session, job_id)
    events = session.scalars(
        select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.created_at)
    ).all()
    return [
        {
            "id": item.id,
            "event_type": item.event_type,
            "from_status": item.from_status,
            "to_status": item.to_status,
            "message": item.message,
            "details": item.details,
            "created_at": item.created_at,
        }
        for item in events
    ]


@router.get("/import/jobs/{job_id}/quality-report")
def job_quality_report(job_id: UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    job = get_job(session, job_id)
    return {"job_id": job.id, "status": job.status, "report": job.validation_report}


@router.get("/operations/queue")
def operation_queue(session: Session = Depends(get_db)) -> dict[str, Any]:
    return queue_summary(session)


@router.get("/operations/workers")
def operation_workers(
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    total = session.scalar(select(func.count(WorkerInstance.id))) or 0
    rows = session.scalars(
        select(WorkerInstance)
        .order_by(WorkerInstance.last_heartbeat_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [
            {
                "id": item.id,
                "worker_identifier": item.worker_identifier,
                "status": item.status,
                "last_heartbeat_at": item.last_heartbeat_at,
                "current_job_id": item.current_job_id,
            }
            for item in rows
        ],
        "meta": {"page": page, "page_size": page_size, "total": total},
    }


@router.get("/operations/health")
def operation_health(session: Session = Depends(get_db)) -> dict[str, Any]:
    queue = queue_summary(session)
    latest_worker = session.scalar(
        select(WorkerInstance).order_by(WorkerInstance.last_heartbeat_at.desc())
    )
    worker_status = "unconfigured"
    if latest_worker:
        age = datetime.now(UTC) - latest_worker.last_heartbeat_at
        worker_status = "healthy" if age < timedelta(minutes=2) else "unavailable"
    enabled_providers = session.scalars(
        select(Provider).where(Provider.is_enabled.is_(True)).order_by(Provider.code)
    ).all()
    status_value = "healthy"
    if queue["failed"]:
        status_value = "degraded"
    return {
        "status": status_value,
        "database": "healthy",
        "worker": worker_status,
        "queue": queue,
        "providers": [
            {
                "code": provider.code,
                "configuration": "configured" if provider.is_enabled else "unconfigured",
                "health": provider.health,
                "last_successful_import_at": provider.last_successful_import_at,
                "stale": provider.last_successful_import_at is None
                or datetime.now(UTC) - provider.last_successful_import_at > timedelta(days=7),
            }
            for provider in enabled_providers
        ],
    }


@router.post("/operations/recover-abandoned")
def recover_operations(request: Request, session: Session = Depends(get_db)) -> dict[str, Any]:
    _guard(request)
    recovered = recover_abandoned_jobs(session)
    session.commit()
    return {"recovered_job_ids": recovered, "count": len(recovered)}


@router.post("/import/schedules", status_code=status.HTTP_201_CREATED)
def create_schedule(payload: ScheduleCreate, session: Session = Depends(get_db)) -> dict[str, Any]:
    provider = session.get(Provider, payload.provider_id)
    if provider is None:
        raise _error("provider_not_found", "Provider was not found", 404)
    value = ImportSchedule(
        provider_id=provider.id,
        name=payload.name,
        symbols=sorted({item.strip().upper() for item in payload.symbols}),
        date_range_policy={"lookback_days": payload.lookback_days},
        mode=payload.mode,
        adjustment_preference=payload.adjustment_preference,
        timezone=payload.timezone,
        is_enabled=payload.is_enabled,
        next_run_at=payload.next_run_at,
    )
    session.add(value)
    try:
        session.commit()
    except Exception as exc:
        session.rollback()
        raise _error("schedule_conflict", "Schedule name already exists", 409) from exc
    return _schedule(value)


@router.get("/import/schedules")
def list_schedules(
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
    enabled: bool | None = None,
    provider_id: UUID | None = None,
    sort: str = Query(default="name", pattern="^(name|next_run_at)$"),
) -> list[dict[str, Any]]:
    filters = []
    if enabled is not None:
        filters.append(ImportSchedule.is_enabled == enabled)
    if provider_id is not None:
        filters.append(ImportSchedule.provider_id == provider_id)
    order = ImportSchedule.next_run_at if sort == "next_run_at" else ImportSchedule.name
    return [
        _schedule(item)
        for item in session.scalars(
            select(ImportSchedule)
            .where(*filters)
            .order_by(order)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    ]


@router.get("/import/schedules/{schedule_id}")
def schedule_detail(schedule_id: UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    value = session.get(ImportSchedule, schedule_id)
    if value is None:
        raise _error("schedule_not_found", "Schedule was not found", 404)
    return _schedule(value)


@router.patch("/import/schedules/{schedule_id}")
def update_schedule(
    schedule_id: UUID, payload: ScheduleUpdate, session: Session = Depends(get_db)
) -> dict[str, Any]:
    value = session.get(ImportSchedule, schedule_id)
    if value is None:
        raise _error("schedule_not_found", "Schedule was not found", 404)
    changes = payload.model_dump(exclude_unset=True)
    lookback = changes.pop("lookback_days", None)
    for key, item in changes.items():
        setattr(value, key, item)
    if lookback is not None:
        value.date_range_policy = {**value.date_range_policy, "lookback_days": lookback}
    session.commit()
    return _schedule(value)


@router.delete("/import/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(schedule_id: UUID, session: Session = Depends(get_db)) -> None:
    value = session.get(ImportSchedule, schedule_id)
    if value is None:
        raise _error("schedule_not_found", "Schedule was not found", 404)
    session.delete(value)
    session.commit()


@router.post("/import/schedules/{schedule_id}/run-now")
def run_schedule_now(schedule_id: UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    value = session.get(ImportSchedule, schedule_id)
    if value is None:
        raise _error("schedule_not_found", "Schedule was not found", 404)
    value.next_run_at = datetime.now(UTC)
    process_due_schedules(session)
    schedule_run = session.scalar(
        select(ScheduleRun)
        .where(ScheduleRun.schedule_id == value.id)
        .order_by(ScheduleRun.scheduled_for.desc())
    )
    session.commit()
    return {
        "schedule_id": value.id,
        "job_id": schedule_run.job_id if schedule_run else None,
        "status": "queued",
    }


@router.post("/reconciliation/preview")
def reconciliation_preview(
    payload: ReconciliationRequest, session: Session = Depends(get_db)
) -> dict[str, Any]:
    return preview_reconciliation(
        session, provider_id=payload.provider_id, symbols=payload.symbols or None
    )


@router.post("/reconciliation/run", status_code=status.HTTP_201_CREATED)
def reconciliation_run(
    payload: ReconciliationRequest, session: Session = Depends(get_db)
) -> dict[str, Any]:
    value = run_reconciliation(
        session,
        provider_id=payload.provider_id,
        symbols=payload.symbols or None,
        dry_run=payload.dry_run,
    )
    session.commit()
    return {
        "id": value.id,
        "status": value.status,
        "dry_run": value.dry_run,
        "issue_count": value.issue_count,
    }


@router.get("/reconciliation/reports")
def reconciliation_reports(
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
    run_status: str | None = Query(default=None, alias="status"),
    dry_run: bool | None = None,
) -> list[dict[str, Any]]:
    filters = []
    if run_status:
        filters.append(ReconciliationRun.status == run_status)
    if dry_run is not None:
        filters.append(ReconciliationRun.dry_run == dry_run)
    rows = session.scalars(
        select(ReconciliationRun)
        .where(*filters)
        .order_by(desc(ReconciliationRun.started_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [
        {
            "id": item.id,
            "status": item.status,
            "dry_run": item.dry_run,
            "records_checked": item.records_checked,
            "issue_count": item.issue_count,
            "started_at": item.started_at,
        }
        for item in rows
    ]


@router.get("/reconciliation/reports/{run_id}")
def reconciliation_report(run_id: UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    value = session.get(ReconciliationRun, run_id)
    if value is None:
        raise _error("reconciliation_not_found", "Reconciliation report was not found", 404)
    issues = session.scalars(
        select(ReconciliationIssue).where(ReconciliationIssue.run_id == run_id)
    ).all()
    return {
        "id": value.id,
        "status": value.status,
        "dry_run": value.dry_run,
        "records_checked": value.records_checked,
        "issue_count": value.issue_count,
        "issues": [
            {
                "id": item.id,
                "type": item.issue_type,
                "severity": item.severity,
                "record": item.record_identifier,
                "outcome": item.outcome,
                "resolution": item.resolution_decision,
            }
            for item in issues
        ],
    }
