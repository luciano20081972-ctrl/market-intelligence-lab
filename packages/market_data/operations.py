from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from packages.database.models import (
    ImportJob,
    ImportSchedule,
    JobEvent,
    JobLease,
    OperationalMetric,
    Provider,
    ScheduleRun,
    WorkerInstance,
)
from packages.market_data.ingestion import create_import_job, run_import_job
from packages.market_data.registry import ProviderRegistry, default_registry

STATE_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running", "cancelled"},
    "running": {"succeeded", "retrying", "failed", "cancelled", "dead_letter"},
    "retrying": {"running", "cancelled", "dead_letter"},
    "interrupted": {"running", "cancelled", "dead_letter"},
    "failed": {"queued", "dead_letter"},
    "cancelled": {"queued"},
    "succeeded": set(),
    "dead_letter": set(),
}


def transition_job(
    session: Session,
    job: ImportJob,
    to_status: str,
    *,
    event_type: str = "state_transition",
    message: str = "",
    details: dict[str, Any] | None = None,
) -> None:
    if to_status not in STATE_TRANSITIONS.get(job.status, set()):
        raise ValueError(f"invalid import-job transition {job.status} -> {to_status}")
    previous = job.status
    job.status = to_status
    session.add(
        JobEvent(
            job_id=job.id,
            event_type=event_type,
            from_status=previous,
            to_status=to_status,
            message=message,
            details=details or {},
        )
    )


def register_worker(
    session: Session, worker_identifier: str, metadata: dict[str, Any] | None = None
) -> WorkerInstance:
    worker = session.scalar(
        select(WorkerInstance).where(WorkerInstance.worker_identifier == worker_identifier)
    )
    now = datetime.now(UTC)
    if worker is None:
        worker = WorkerInstance(
            worker_identifier=worker_identifier,
            status="idle",
            started_at=now,
            last_heartbeat_at=now,
            metadata_json=metadata or {},
        )
        session.add(worker)
    else:
        worker.status = "idle"
        worker.started_at = now
        worker.last_heartbeat_at = now
        worker.stopped_at = None
        worker.metadata_json = metadata or worker.metadata_json
    session.flush()
    return worker


def heartbeat_worker(session: Session, worker: WorkerInstance) -> None:
    worker.last_heartbeat_at = datetime.now(UTC)
    if worker.status == "starting":
        worker.status = "idle"
    session.flush()


def claim_next_job(
    session: Session,
    worker: WorkerInstance,
    *,
    lease_seconds: int = 60,
    now: datetime | None = None,
) -> tuple[ImportJob, JobLease] | None:
    current = now or datetime.now(UTC)
    candidate = session.scalar(
        select(ImportJob)
        .where(
            ImportJob.cancel_requested.is_(False),
            or_(
                ImportJob.status == "queued",
                (ImportJob.status == "retrying")
                & (ImportJob.next_retry_at.is_(None) | (ImportJob.next_retry_at <= current)),
                ImportJob.status == "interrupted",
            ),
            ~select(JobLease.id).where(JobLease.job_id == ImportJob.id).exists(),
        )
        .order_by(ImportJob.requested_at, ImportJob.id)
        .limit(1)
    )
    if candidate is None:
        return None
    previous = candidate.status
    claimed = session.execute(
        update(ImportJob)
        .where(ImportJob.id == candidate.id, ImportJob.status == previous)
        .values(status="running", started_at=func.coalesce(ImportJob.started_at, current))
    )
    if getattr(claimed, "rowcount", 0) != 1:
        session.rollback()
        return None
    lease = JobLease(
        job_id=candidate.id,
        worker_id=worker.id,
        lease_token=secrets.token_hex(24),
        acquired_at=current,
        heartbeat_at=current,
        expires_at=current + timedelta(seconds=lease_seconds),
    )
    session.add(lease)
    worker.status = "running"
    worker.current_job_id = candidate.id
    worker.last_heartbeat_at = current
    session.add(
        JobEvent(
            job_id=candidate.id,
            event_type="claimed",
            from_status=previous,
            to_status="running",
            message="Job claimed by single-process worker",
            details={"worker_identifier": worker.worker_identifier},
        )
    )
    session.flush()
    session.refresh(candidate)
    return candidate, lease


def renew_lease(
    session: Session,
    lease: JobLease,
    worker: WorkerInstance,
    *,
    lease_seconds: int = 60,
) -> None:
    if lease.worker_id != worker.id:
        raise ValueError("worker does not own this lease")
    now = datetime.now(UTC)
    if lease.expires_at <= now:
        raise ValueError("job lease has expired")
    lease.heartbeat_at = now
    lease.expires_at = now + timedelta(seconds=lease_seconds)
    worker.last_heartbeat_at = now
    session.flush()


def release_lease(session: Session, lease: JobLease, worker: WorkerInstance) -> None:
    if lease.worker_id != worker.id:
        raise ValueError("worker does not own this lease")
    session.delete(lease)
    worker.current_job_id = None
    worker.status = "idle"
    worker.last_heartbeat_at = datetime.now(UTC)
    session.flush()


def execute_claimed_job(
    session: Session,
    job: ImportJob,
    lease: JobLease,
    worker: WorkerInstance,
    registry: ProviderRegistry = default_registry,
    heartbeat: Callable[[], None] | None = None,
) -> ImportJob:
    if lease.job_id != job.id or lease.worker_id != worker.id:
        raise ValueError("job lease ownership mismatch")
    run_import_job(session, job, registry, heartbeat=heartbeat)
    for name, value in {
        "import_duration_ms": job.processing_duration_ms,
        "records_fetched": job.records_processed,
        "records_accepted": job.records_inserted,
        "records_rejected": job.records_skipped,
        "retry_count": max(job.attempt - 1, 0),
    }.items():
        session.add(
            OperationalMetric(
                metric_name=name,
                metric_value=Decimal(value),
                labels={"provider_id": str(job.provider_id), "status": job.status},
                job_id=job.id,
                worker_id=worker.id,
            )
        )
    session.add(
        JobEvent(
            job_id=job.id,
            event_type="completed" if job.status == "succeeded" else "attempt_finished",
            from_status="running",
            to_status=job.status,
            message=job.error_summary or "Import attempt finished",
            details={
                "records_processed": job.records_processed,
                "records_inserted": job.records_inserted,
                "records_skipped": job.records_skipped,
                "attempt": job.attempt,
            },
        )
    )
    release_lease(session, lease, worker)
    return job


def recover_abandoned_jobs(session: Session, *, now: datetime | None = None) -> list[UUID]:
    current = now or datetime.now(UTC)
    leases = session.scalars(select(JobLease).where(JobLease.expires_at <= current)).all()
    recovered: list[UUID] = []
    for lease in leases:
        job = session.get(ImportJob, lease.job_id)
        worker = session.get(WorkerInstance, lease.worker_id)
        if job is not None and job.status == "running":
            target = "retrying" if job.attempt < job.max_attempts else "dead_letter"
            job.status = target
            job.next_retry_at = current if target == "retrying" else None
            job.error_summary = "Worker lease expired; job recovered"
            session.add(
                JobEvent(
                    job_id=job.id,
                    event_type="lease_expired",
                    from_status="running",
                    to_status=target,
                    message="Abandoned job recovered after lease expiry",
                )
            )
            recovered.append(job.id)
        if worker is not None:
            worker.status = "unavailable"
            worker.current_job_id = None
        session.delete(lease)
    session.flush()
    return recovered


def process_due_schedules(session: Session, *, now: datetime | None = None) -> list[ImportJob]:
    current = now or datetime.now(UTC)
    schedules = session.scalars(
        select(ImportSchedule)
        .where(ImportSchedule.is_enabled.is_(True), ImportSchedule.next_run_at <= current)
        .order_by(ImportSchedule.next_run_at)
    ).all()
    jobs: list[ImportJob] = []
    for schedule in schedules:
        due = schedule.next_run_at
        existing = session.scalar(
            select(ScheduleRun).where(
                ScheduleRun.schedule_id == schedule.id, ScheduleRun.scheduled_for == due
            )
        )
        if existing is not None:
            continue
        provider = session.get(Provider, schedule.provider_id)
        if provider is None:
            schedule.failure_count += 1
            schedule.last_error = "Provider not found"
            continue
        days = int(schedule.date_range_policy.get("lookback_days", 7))
        key_payload = f"schedule:{schedule.id}:{due.isoformat()}"
        job = create_import_job(
            session,
            provider_code=provider.code,
            symbols=schedule.symbols,
            mode=schedule.mode,
            start=current - timedelta(days=days),
            end=current,
            adjustment_preference=schedule.adjustment_preference,
            idempotency_key=hashlib.sha256(key_payload.encode()).hexdigest(),
            queue_name="daily",
        )
        session.add(
            ScheduleRun(
                schedule_id=schedule.id,
                job_id=job.id,
                scheduled_for=due,
                status="queued",
            )
        )
        schedule.last_run_at = current
        schedule.next_run_at = due + timedelta(days=1)
        schedule.last_error = None
        jobs.append(job)
    session.flush()
    return jobs


def queue_summary(session: Session) -> dict[str, Any]:
    counts: dict[str, int] = {
        status: count
        for status, count in session.execute(
            select(ImportJob.status, func.count(ImportJob.id)).group_by(ImportJob.status)
        ).all()
    }
    return {
        "depth": sum(counts.get(status, 0) for status in ("queued", "retrying", "interrupted")),
        "failed": counts.get("failed", 0) + counts.get("dead_letter", 0),
        "running": counts.get("running", 0),
        "by_status": counts,
    }


def job_fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def stop_worker(session: Session, worker: WorkerInstance) -> None:
    worker.status = "stopped"
    worker.stopped_at = datetime.now(UTC)
    worker.current_job_id = None
    session.execute(delete(JobLease).where(JobLease.worker_id == worker.id))
    session.flush()
