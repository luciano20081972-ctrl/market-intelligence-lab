from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db, get_workspace_context
from apps.api.schemas_phase5 import ComputeJobCreate, ComputeRetryRequest
from packages.compute.budget import BudgetLimits
from packages.compute.resource_guard import ResourceSnapshot
from packages.compute.router import ComputeRouter, ProviderAvailability
from packages.compute.service import (
    budget_usage,
    cancel_job,
    create_and_route_job,
    retry_job,
    running_local_jobs,
)
from packages.compute.types import ComputeJobSpec, ComputeState, ResourceEstimate
from packages.core.config import Settings
from packages.database.models import (
    AlertEvent,
    CloudUsageLedger,
    ComputeJob,
    ComputeJobTransition,
    DataFreshnessObservation,
    DecisionSignal,
    MarketSupervisorHeartbeat,
)
from packages.security import WorkspaceContext
from packages.supervisor.safety import assert_research_or_paper_only
from packages.supervisor.worker import resource_guard

router = APIRouter(tags=["compute-control-plane"])


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _limits(settings: Settings) -> BudgetLimits:
    return BudgetLimits(
        cloud_enabled=settings.cloud_compute_enabled,
        max_job_usd=Decimal(str(settings.max_cloud_job_estimated_usd)),
        max_daily_usd=Decimal(str(settings.max_daily_cloud_compute_usd)),
        max_monthly_usd=Decimal(str(settings.max_monthly_cloud_compute_usd)),
        max_parallel_tasks=settings.max_parallel_cloud_tasks,
        max_runtime_seconds=settings.max_cloud_job_runtime,
        spend_cap_blocked=settings.cloud_spend_cap_blocked,
    )


def _availability(settings: Settings) -> ProviderAvailability:
    configured = bool(
        settings.cloud_compute_enabled
        and settings.cloud_project_id
        and settings.cloud_region
        and settings.cloud_run_job_name
        and settings.cloud_worker_image
        and settings.cloud_input_bucket
        and settings.cloud_result_bucket
    )
    return ProviderAvailability(cloud_run=configured, google_batch=False)


def _job(value: ComputeJob) -> dict[str, Any]:
    return {
        "id": value.id,
        "submission_key": value.submission_key,
        "job_type": value.job_type,
        "job_class": value.job_class,
        "state": value.state,
        "priority": value.priority,
        "selected_provider": value.selected_provider,
        "estimate": {
            "cpu": value.estimated_cpu,
            "ram_mb": value.estimated_ram_mb,
            "runtime_seconds": value.estimated_runtime_seconds,
            "estimated_cost_usd": value.estimated_cost_usd,
            "task_count": value.parameters.get("task_count", 1),
        },
        "attempt_count": value.attempt_count,
        "max_attempts": value.max_attempts,
        "cancel_requested": bool(value.parameters.get("cancel_requested")),
        "symbols": value.symbols,
        "input_manifest_hash": value.input_manifest_hash,
        "result_manifest": value.result_manifest,
        "error_classification": value.error_classification,
        "error_detail": value.error_detail,
        "created_at": value.created_at,
        "started_at": value.started_at,
        "completed_at": value.completed_at,
        "updated_at": value.updated_at,
    }


@router.get("/compute/status")
def compute_status(
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    settings = _settings(request)
    guard = resource_guard(settings)
    live = guard.snapshot()
    snapshot = ResourceSnapshot(
        live.available_ram_mb,
        live.load_1m,
        live.cpu_count,
        running_local_jobs(session),
    )
    counts: dict[str, int] = {
        str(state): int(count)
        for state, count in session.execute(
            select(ComputeJob.state, func.count(ComputeJob.id))
            .where(ComputeJob.workspace_id == context.workspace_id)
            .group_by(ComputeJob.state)
        ).tuples()
    }
    heartbeat = session.scalar(
        select(MarketSupervisorHeartbeat).order_by(MarketSupervisorHeartbeat.heartbeat_at.desc())
    )
    cloud_health = (
        str(heartbeat.provider_health.get("cloud_run", "unknown")) if heartbeat else "not_reported"
    )
    return {
        "cloud_enabled": settings.cloud_compute_enabled,
        "cloud_configured": _availability(settings).cloud_run,
        "providers": {
            "local": "available",
            "cloud_run": cloud_health,
            "google_batch": "future_provider",
        },
        "resource_guard": {
            "available_ram_mb": snapshot.available_ram_mb,
            "load_per_cpu": snapshot.load_per_cpu,
            "running_analytical_jobs": snapshot.running_analytical_jobs,
        },
        "job_counts": counts,
    }


@router.post("/compute/jobs", status_code=201)
def submit_compute_job(
    payload: ComputeJobCreate,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        assert_research_or_paper_only(
            {
                "parameters": payload.parameters,
                "input_manifest": payload.input_manifest,
                "data_provenance": payload.data_provenance,
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    settings = _settings(request)
    guard = resource_guard(settings)
    live = guard.snapshot()
    spec = ComputeJobSpec(
        workspace_id=context.workspace_id,
        requested_by=context.user_id,
        submission_key=payload.submission_key,
        job_type=payload.job_type,
        job_class=payload.job_class,
        estimate=ResourceEstimate(
            payload.estimate.cpu,
            payload.estimate.ram_mb,
            payload.estimate.runtime_seconds,
            payload.estimate.estimated_cost_usd,
            payload.estimate.task_count,
        ),
        priority=payload.priority,
        deadline=payload.deadline,
        symbols=tuple(payload.symbols),
        date_start=payload.date_start,
        date_end=payload.date_end,
        parameters=payload.parameters,
        strategy_version=payload.strategy_version,
        hypothesis_version=payload.hypothesis_version,
        model_version=payload.model_version,
        input_manifest=payload.input_manifest,
        input_manifest_hash=payload.input_manifest_hash,
        data_provenance=payload.data_provenance,
        data_version=payload.data_version,
        max_attempts=payload.max_attempts,
        max_cost_usd=payload.max_cost_usd,
    )
    job, created, decision = create_and_route_job(
        session,
        spec,
        router=ComputeRouter(guard),
        snapshot=ResourceSnapshot(
            live.available_ram_mb, live.load_1m, live.cpu_count, running_local_jobs(session)
        ),
        limits=_limits(settings),
        availability=_availability(settings),
    )
    session.commit()
    return {"created": created, "route_reason": decision.reason, "job": _job(job)}


@router.get("/compute/jobs")
def list_compute_jobs(
    context: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db),
    state: ComputeState | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    query = select(ComputeJob).where(ComputeJob.workspace_id == context.workspace_id)
    if state:
        query = query.where(ComputeJob.state == state.value)
    return [
        _job(item)
        for item in session.scalars(query.order_by(ComputeJob.created_at.desc()).limit(limit))
    ]


@router.get("/compute/jobs/{job_id}")
def get_compute_job(
    job_id: UUID,
    context: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    job = session.scalar(
        select(ComputeJob).where(
            ComputeJob.id == job_id, ComputeJob.workspace_id == context.workspace_id
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Compute job was not found")
    transitions = session.scalars(
        select(ComputeJobTransition)
        .where(ComputeJobTransition.job_id == job.id)
        .order_by(ComputeJobTransition.created_at)
    ).all()
    ledger = session.scalars(
        select(CloudUsageLedger).where(CloudUsageLedger.job_id == job.id)
    ).all()
    observed = [item.observed_usd for item in ledger if item.observed_usd is not None]
    return {
        **_job(job),
        "input_manifest": job.input_manifest,
        "data_provenance": job.data_provenance,
        "observed_cost_usd": sum(observed, Decimal("0")) if observed else None,
        "cost_observation_status": "observed" if observed else "provider_billing_pending",
        "transitions": [
            {
                "from_state": item.from_state,
                "to_state": item.to_state,
                "reason": item.reason,
                "details": item.details,
                "created_at": item.created_at,
            }
            for item in transitions
        ],
    }


@router.post("/compute/jobs/{job_id}/cancel")
def cancel_compute_job(
    job_id: UUID,
    context: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    job = session.scalar(
        select(ComputeJob).where(
            ComputeJob.id == job_id, ComputeJob.workspace_id == context.workspace_id
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Compute job was not found")
    cancel_job(session, job)
    session.commit()
    return _job(job)


@router.post("/compute/jobs/{job_id}/retry")
def retry_compute_job(
    job_id: UUID,
    payload: ComputeRetryRequest,
    context: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    job = session.scalar(
        select(ComputeJob).where(
            ComputeJob.id == job_id, ComputeJob.workspace_id == context.workspace_id
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Compute job was not found")
    try:
        retry_job(
            session,
            job,
            confirm_no_cloud_execution=payload.confirm_no_cloud_execution,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return _job(job)


@router.get("/compute/budget")
def compute_budget(
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    limits = _limits(_settings(request))
    usage = budget_usage(session, context.workspace_id)
    return {
        "cloud_enabled": limits.cloud_enabled,
        "spend_cap_blocked": limits.spend_cap_blocked,
        "limits": {
            "job_usd": limits.max_job_usd,
            "daily_usd": limits.max_daily_usd,
            "monthly_usd": limits.max_monthly_usd,
            "parallel_tasks": limits.max_parallel_tasks,
            "runtime_seconds": limits.max_runtime_seconds,
        },
        "usage": {
            "daily_usd": usage.daily_usd,
            "monthly_usd": usage.monthly_usd,
            "active_tasks": usage.active_tasks,
        },
    }


@router.get("/market/status")
def market_status(
    context: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    heartbeat = session.scalar(
        select(MarketSupervisorHeartbeat).order_by(MarketSupervisorHeartbeat.heartbeat_at.desc())
    )
    cutoff = datetime.now(UTC) - timedelta(minutes=2)
    freshness: dict[str, int] = {
        str(classification): int(count)
        for classification, count in session.execute(
            select(DataFreshnessObservation.classification, func.count(DataFreshnessObservation.id))
            .where(
                DataFreshnessObservation.workspace_id == context.workspace_id,
                DataFreshnessObservation.processed_at >= cutoff,
            )
            .group_by(DataFreshnessObservation.classification)
        ).tuples()
    }
    return {
        "supervisor": {
            "status": "healthy" if heartbeat and heartbeat.heartbeat_at >= cutoff else "stale",
            "instance_id": heartbeat.instance_id if heartbeat else None,
            "heartbeat_at": heartbeat.heartbeat_at if heartbeat else None,
            "session_state": heartbeat.session_state if heartbeat else "UNKNOWN",
            "last_signal_scan_at": heartbeat.last_signal_scan_at if heartbeat else None,
            "providers": heartbeat.provider_health if heartbeat else {},
            "last_error": heartbeat.last_error if heartbeat else None,
        },
        "freshness_last_two_minutes": freshness,
    }


@router.get("/signals")
def decision_signals(
    context: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(DecisionSignal)
        .where(DecisionSignal.workspace_id == context.workspace_id)
        .order_by(DecisionSignal.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": row.id,
            "symbol": row.symbol,
            "decision": row.decision,
            "confidence": row.confidence,
            "horizon": row.horizon,
            "market_regime": row.market_regime,
            "evidence": row.evidence,
            "contradicting_signals": row.contradicting_signals,
            "entry_zone": row.entry_zone,
            "invalidation_rule": row.invalidation_rule,
            "risk_reference": row.risk_reference,
            "freshness": row.freshness,
            "strategy_version": row.strategy_version,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/alerts")
def alert_events(
    context: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(AlertEvent)
        .where(AlertEvent.workspace_id == context.workspace_id)
        .order_by(AlertEvent.last_seen_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": row.id,
            "category": row.category,
            "severity": row.severity,
            "title": row.title,
            "message": row.message,
            "payload": row.payload,
            "status": row.status,
            "occurrence_count": row.occurrence_count,
            "last_seen_at": row.last_seen_at,
            "created_at": row.created_at,
        }
        for row in rows
    ]
