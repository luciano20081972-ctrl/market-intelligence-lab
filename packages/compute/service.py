from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.compute.budget import BudgetLimits, BudgetUsage
from packages.compute.manifests import canonical_checksum
from packages.compute.resource_guard import LocalResourceGuard, ResourceSnapshot
from packages.compute.router import ComputeRouter, ProviderAvailability, RouteDecision
from packages.compute.types import (
    ComputeJobSpec,
    ComputeProviderName,
    ComputeState,
    JobClass,
    ResourceEstimate,
)
from packages.core.time import utc_now
from packages.database.models import CloudUsageLedger, ComputeJob, ComputeJobTransition

ALLOWED_TRANSITIONS: dict[ComputeState, set[ComputeState]] = {
    ComputeState.ESTIMATING: {ComputeState.ROUTING, ComputeState.FAILED_FINAL},
    ComputeState.ROUTING: {
        ComputeState.QUEUED,
        ComputeState.CLOUD_SUBMITTING,
        ComputeState.WAITING_FOR_CAPACITY,
        ComputeState.CLOUD_DISABLED,
        ComputeState.BLOCKED_BY_BUDGET,
        ComputeState.FAILED_FINAL,
    },
    ComputeState.QUEUED: {
        ComputeState.LOCAL_RUNNING,
        ComputeState.WAITING_FOR_CAPACITY,
        ComputeState.CANCELED,
    },
    ComputeState.LOCAL_RUNNING: {
        ComputeState.CHECKPOINTED,
        ComputeState.RESULT_VALIDATING,
        ComputeState.SUCCEEDED,
        ComputeState.FAILED_RETRYABLE,
        ComputeState.FAILED_FINAL,
        ComputeState.CANCELED,
    },
    ComputeState.CLOUD_SUBMITTING: {
        ComputeState.CLOUD_QUEUED,
        ComputeState.FAILED_RETRYABLE,
        ComputeState.FAILED_FINAL,
        ComputeState.CANCELED,
    },
    ComputeState.CLOUD_QUEUED: {
        ComputeState.CLOUD_RUNNING,
        ComputeState.FAILED_RETRYABLE,
        ComputeState.CANCELED,
    },
    ComputeState.CLOUD_RUNNING: {
        ComputeState.CHECKPOINTED,
        ComputeState.RESULT_VALIDATING,
        ComputeState.FAILED_RETRYABLE,
        ComputeState.FAILED_FINAL,
        ComputeState.CANCELED,
    },
    ComputeState.CHECKPOINTED: {
        ComputeState.LOCAL_RUNNING,
        ComputeState.CLOUD_RUNNING,
        ComputeState.RESULT_VALIDATING,
        ComputeState.CANCELED,
    },
    ComputeState.RESULT_VALIDATING: {
        ComputeState.SUCCEEDED,
        ComputeState.FAILED_RETRYABLE,
        ComputeState.FAILED_FINAL,
    },
    ComputeState.FAILED_RETRYABLE: {
        ComputeState.QUEUED,
        ComputeState.CLOUD_SUBMITTING,
        ComputeState.CLOUD_QUEUED,
        ComputeState.FAILED_FINAL,
        ComputeState.CANCELED,
    },
    ComputeState.WAITING_FOR_CAPACITY: {
        ComputeState.ROUTING,
        ComputeState.CANCELED,
    },
    ComputeState.CLOUD_DISABLED: {ComputeState.ROUTING, ComputeState.CANCELED},
    ComputeState.BLOCKED_BY_BUDGET: {ComputeState.ROUTING, ComputeState.CANCELED},
}


def transition_job(
    session: Session,
    job: ComputeJob,
    target: ComputeState,
    reason: str,
    details: dict[str, Any] | None = None,
) -> None:
    current = ComputeState(job.state)
    if target != current and target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"invalid compute transition {current} -> {target}")
    session.add(
        ComputeJobTransition(
            job_id=job.id,
            from_state=current.value,
            to_state=target.value,
            reason=reason[:240],
            details=details or {},
        )
    )
    job.state = target.value
    job.updated_at = utc_now()
    if target in {ComputeState.LOCAL_RUNNING, ComputeState.CLOUD_RUNNING} and not job.started_at:
        job.started_at = utc_now()
    if target in {
        ComputeState.SUCCEEDED,
        ComputeState.FAILED_FINAL,
        ComputeState.CANCELED,
    }:
        job.completed_at = utc_now()


def budget_usage(session: Session, workspace_id: UUID, now: datetime | None = None) -> BudgetUsage:
    current = now or datetime.now(UTC)
    daily = session.scalar(
        select(func.coalesce(func.sum(CloudUsageLedger.estimated_usd), 0)).where(
            CloudUsageLedger.workspace_id == workspace_id,
            CloudUsageLedger.usage_date == current.date(),
        )
    )
    month_start = date(current.year, current.month, 1)
    monthly = session.scalar(
        select(func.coalesce(func.sum(CloudUsageLedger.estimated_usd), 0)).where(
            CloudUsageLedger.workspace_id == workspace_id,
            CloudUsageLedger.usage_date >= month_start,
            CloudUsageLedger.usage_date <= current.date(),
        )
    )
    active = session.scalar(
        select(func.coalesce(func.sum(CloudUsageLedger.task_count), 0))
        .join(ComputeJob, ComputeJob.id == CloudUsageLedger.job_id)
        .where(
            CloudUsageLedger.workspace_id == workspace_id,
            ComputeJob.state.in_(
                [
                    ComputeState.CLOUD_SUBMITTING.value,
                    ComputeState.CLOUD_QUEUED.value,
                    ComputeState.CLOUD_RUNNING.value,
                ]
            ),
        )
    )
    return BudgetUsage(Decimal(str(daily or 0)), Decimal(str(monthly or 0)), int(active or 0))


def running_local_jobs(session: Session) -> int:
    return int(
        session.scalar(
            select(func.count(ComputeJob.id)).where(
                ComputeJob.state == ComputeState.LOCAL_RUNNING.value
            )
        )
        or 0
    )


def spec_from_job(job: ComputeJob) -> ComputeJobSpec:
    return ComputeJobSpec(
        job_id=job.id,
        workspace_id=job.workspace_id,
        requested_by=job.requested_by_user_id,
        submission_key=job.submission_key,
        job_type=job.job_type,
        job_class=JobClass(job.job_class),
        estimate=ResourceEstimate(
            Decimal(str(job.estimated_cpu)),
            job.estimated_ram_mb,
            job.estimated_runtime_seconds,
            Decimal(str(job.estimated_cost_usd)),
            int(job.parameters.get("task_count") or 1),
        ),
        priority=job.priority,
        deadline=job.deadline,
        symbols=tuple(job.symbols),
        date_start=job.date_start,
        date_end=job.date_end,
        parameters=job.parameters,
        strategy_version=job.strategy_version,
        hypothesis_version=job.hypothesis_version,
        model_version=job.model_version,
        input_manifest=job.input_manifest,
        input_manifest_hash=job.input_manifest_hash,
        data_provenance=job.data_provenance,
        data_version=job.data_version,
        max_attempts=job.max_attempts,
        max_cost_usd=job.max_cost_usd,
    )


def create_and_route_job(
    session: Session,
    spec: ComputeJobSpec,
    *,
    router: ComputeRouter,
    snapshot: ResourceSnapshot,
    limits: BudgetLimits,
    availability: ProviderAvailability,
) -> tuple[ComputeJob, bool, RouteDecision]:
    existing = session.scalar(
        select(ComputeJob).where(
            ComputeJob.workspace_id == spec.workspace_id,
            ComputeJob.submission_key == spec.submission_key,
        )
    )
    if existing is not None:
        return (
            existing,
            False,
            RouteDecision(
                ComputeState(existing.state),
                None
                if existing.selected_provider is None
                else ComputeProviderName(existing.selected_provider),
                "idempotent_existing_submission",
            ),
        )
    manifest_hash = spec.input_manifest_hash or canonical_checksum(spec.input_manifest)
    job = ComputeJob(
        id=spec.job_id,
        workspace_id=spec.workspace_id,
        requested_by_user_id=spec.requested_by,
        submission_key=spec.submission_key,
        job_type=spec.job_type,
        job_class=spec.job_class.value,
        priority=spec.priority,
        state=ComputeState.ESTIMATING.value,
        deadline=spec.deadline,
        symbols=list(spec.symbols),
        date_start=spec.date_start,
        date_end=spec.date_end,
        parameters={**spec.parameters, "task_count": spec.estimate.task_count},
        strategy_version=spec.strategy_version,
        hypothesis_version=spec.hypothesis_version,
        model_version=spec.model_version,
        input_manifest=spec.input_manifest,
        input_manifest_hash=manifest_hash,
        data_provenance=spec.data_provenance,
        data_version=spec.data_version,
        estimated_cpu=spec.estimate.cpu,
        estimated_ram_mb=spec.estimate.ram_mb,
        estimated_runtime_seconds=spec.estimate.runtime_seconds,
        estimated_cost_usd=spec.estimate.estimated_cost_usd,
        max_cost_usd=spec.max_cost_usd,
        attempt_count=0,
        max_attempts=spec.max_attempts,
        checkpoint_state={},
        result_manifest={},
    )
    session.add(job)
    session.flush()
    session.add(
        ComputeJobTransition(
            job_id=job.id,
            from_state=None,
            to_state=ComputeState.ESTIMATING.value,
            reason="job_created",
            details={"submission_key": spec.submission_key},
        )
    )
    transition_job(session, job, ComputeState.ROUTING, "estimate_completed")
    decision = router.route(
        spec, snapshot, limits, budget_usage(session, spec.workspace_id), availability
    )
    job.selected_provider = decision.provider.value if decision.provider else None
    transition_job(
        session,
        job,
        decision.state,
        decision.reason,
        {"provider": job.selected_provider, "estimated_cost_usd": str(job.estimated_cost_usd)},
    )
    return job, True, decision


def cancel_job(session: Session, job: ComputeJob, reason: str = "user_requested") -> ComputeJob:
    if ComputeState(job.state) in {
        ComputeState.SUCCEEDED,
        ComputeState.FAILED_FINAL,
        ComputeState.CANCELED,
    }:
        return job
    if (
        job.selected_provider == ComputeProviderName.GOOGLE_CLOUD_RUN_JOBS.value
        and job.cloud_execution_id
        and ComputeState(job.state) in {ComputeState.CLOUD_QUEUED, ComputeState.CLOUD_RUNNING}
    ):
        job.parameters = {**job.parameters, "cancel_requested": True}
        transition_job(
            session,
            job,
            ComputeState(job.state),
            "cloud_cancel_queued_for_supervisor",
        )
        return job
    transition_job(session, job, ComputeState.CANCELED, reason)
    job.error_classification = "CANCELED"
    return job


def retry_job(
    session: Session,
    job: ComputeJob,
    *,
    confirm_no_cloud_execution: bool = False,
) -> ComputeJob:
    if ComputeState(job.state) != ComputeState.FAILED_RETRYABLE:
        raise ValueError("only retryable failures can be retried")
    if job.attempt_count >= job.max_attempts:
        transition_job(session, job, ComputeState.FAILED_FINAL, "maximum_attempts_reached")
        return job
    if job.selected_provider == ComputeProviderName.LOCAL.value:
        transition_job(session, job, ComputeState.QUEUED, "bounded_local_retry")
        return job
    if job.selected_provider == ComputeProviderName.GOOGLE_CLOUD_RUN_JOBS.value:
        if job.cloud_execution_id:
            transition_job(
                session,
                job,
                ComputeState.CLOUD_QUEUED,
                "reconcile_recorded_cloud_execution",
            )
            return job
        if not confirm_no_cloud_execution:
            raise ValueError(
                "cloud execution absence must be confirmed before a new paid submission"
            )
        transition_job(
            session,
            job,
            ComputeState.CLOUD_SUBMITTING,
            "confirmed_cloud_resubmission",
        )
        return job
    raise ValueError("the selected provider does not support retry")


def reroute_one_held_job(
    session: Session,
    *,
    router: ComputeRouter,
    snapshot: ResourceSnapshot,
    limits: BudgetLimits,
    availability: ProviderAvailability,
    include_cloud_holds: bool,
) -> ComputeJob | None:
    states = [ComputeState.WAITING_FOR_CAPACITY.value]
    if include_cloud_holds:
        states.extend([ComputeState.CLOUD_DISABLED.value, ComputeState.BLOCKED_BY_BUDGET.value])
    job = session.scalar(
        select(ComputeJob)
        .where(
            ComputeJob.state.in_(states),
            ComputeJob.updated_at <= utc_now() - timedelta(minutes=5),
        )
        .order_by(ComputeJob.priority.desc(), ComputeJob.updated_at)
        .limit(1)
    )
    if job is None:
        return None
    transition_job(session, job, ComputeState.ROUTING, "periodic_route_re_evaluation")
    decision = router.route(
        spec_from_job(job),
        snapshot,
        limits,
        budget_usage(session, job.workspace_id),
        availability,
    )
    job.selected_provider = decision.provider.value if decision.provider else None
    transition_job(session, job, decision.state, decision.reason)
    return job


def execute_one_local_job(session: Session, guard: LocalResourceGuard) -> ComputeJob | None:
    job = session.scalar(
        select(ComputeJob)
        .where(
            ComputeJob.state == ComputeState.QUEUED.value,
            ComputeJob.selected_provider == "local",
        )
        .order_by(ComputeJob.priority.desc(), ComputeJob.created_at)
        .limit(1)
    )
    if job is None:
        return None
    live = guard.snapshot()
    snapshot = ResourceSnapshot(
        live.available_ram_mb,
        live.load_1m,
        live.cpu_count,
        running_local_jobs(session),
    )
    decision = guard.evaluate(JobClass(job.job_class), spec_from_job(job).estimate, snapshot)
    if not decision.allowed:
        transition_job(session, job, ComputeState.WAITING_FOR_CAPACITY, decision.reason)
        return job
    transition_job(session, job, ComputeState.LOCAL_RUNNING, "local_worker_claimed")
    job.attempt_count += 1
    if job.job_type not in {"control_plane_health", "deterministic_fixture"}:
        transition_job(
            session,
            job,
            ComputeState.FAILED_FINAL,
            "local_executor_not_registered",
        )
        job.error_classification = "INVALID_INPUT"
        job.error_detail = "No bounded local executor is registered for this job type"
        return job
    result = {
        "job_id": str(job.id),
        "workspace_id": str(job.workspace_id),
        "input_manifest_hash": job.input_manifest_hash,
        "algorithm_version": job.model_version or "phase5-control-plane-v1",
        "provider": "local",
        "status": "validated",
    }
    transition_job(session, job, ComputeState.RESULT_VALIDATING, "local_result_ready")
    job.result_manifest = {**result, "manifest_checksum": canonical_checksum(result)}
    transition_job(session, job, ComputeState.SUCCEEDED, "local_result_validated")
    return job
