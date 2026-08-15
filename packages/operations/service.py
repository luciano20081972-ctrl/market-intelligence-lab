from __future__ import annotations

import hashlib
import random
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.database.models import (
    DataFreshnessStatus,
    OperationalAlert,
    ProviderCircuitBreaker,
    ScheduledTaskDefinition,
    ScheduledTaskOccurrence,
)

RETRYABLE_CATEGORIES = {
    "TRANSIENT_NETWORK",
    "RATE_LIMIT",
    "PROVIDER_5XX",
    "TIMEOUT",
    "TEMPORARY_DATABASE",
    "UNKNOWN",
}
PERMANENT_CATEGORIES = {
    "INVALID_RESPONSE",
    "AUTH_CONFIGURATION",
    "SCHEMA_INCOMPATIBLE",
    "PERMANENT_VALIDATION",
}


def circuit_allows_request(breaker: ProviderCircuitBreaker, *, now: datetime) -> bool:
    if breaker.state in {None, "CLOSED"}:
        return True
    if breaker.state == "OPEN" and breaker.next_probe_at and now >= breaker.next_probe_at:
        breaker.state = "HALF_OPEN"
        return True
    return breaker.state == "HALF_OPEN"


def record_provider_result(
    breaker: ProviderCircuitBreaker,
    *,
    succeeded: bool,
    now: datetime,
    error_category: str | None = None,
    failure_threshold: int = 3,
    cooldown_seconds: int = 300,
) -> None:
    if succeeded:
        breaker.state = "CLOSED"
        breaker.consecutive_failures = 0
        breaker.opened_at = None
        breaker.next_probe_at = None
        breaker.last_error_category = None
        return
    breaker.consecutive_failures = (breaker.consecutive_failures or 0) + 1
    breaker.last_error_category = error_category or "UNKNOWN"
    if breaker.consecutive_failures >= failure_threshold:
        breaker.state = "OPEN"
        breaker.opened_at = now
        breaker.next_probe_at = now + timedelta(seconds=cooldown_seconds)


def admit_work(*, active: int, backlog: int, maximum_active: int, maximum_backlog: int) -> str:
    """Bounded backpressure decision; callers persist DEFER rather than dropping work."""

    if backlog >= maximum_backlog:
        return "DEFER_BACKLOG"
    if active >= maximum_active:
        return "DEFER_CONCURRENCY"
    return "ADMIT"


def compute_retry_delay(
    attempt: int,
    *,
    base_seconds: int = 30,
    maximum_seconds: int = 3600,
    retry_after_seconds: int | None = None,
    jitter_seed: str = "",
) -> timedelta:
    """Return bounded deterministic jitter suitable for persisted retry timestamps."""

    if attempt < 1:
        raise ValueError("attempt must be positive")
    exponential = min(maximum_seconds, base_seconds * (2 ** (attempt - 1)))
    rng = random.Random(f"{jitter_seed}:{attempt}")  # noqa: S311 - deterministic scheduling only
    jittered = min(maximum_seconds, exponential + rng.randint(0, max(1, exponential // 5)))
    if retry_after_seconds is not None:
        jittered = max(jittered, min(maximum_seconds, retry_after_seconds))
    return timedelta(seconds=jittered)


def next_due(definition: ScheduledTaskDefinition, due: datetime) -> datetime:
    schedule = definition.schedule
    schedule_type = definition.schedule_type.upper()
    if schedule_type == "INTERVAL":
        return due + timedelta(seconds=max(60, int(schedule.get("seconds", 3600))))
    if schedule_type == "DAILY":
        return due + timedelta(days=1)
    if schedule_type == "WEEKLY":
        return due + timedelta(days=7)
    if schedule_type in {"MARKET_CALENDAR", "DATASET_CADENCE"}:
        days = max(1, int(schedule.get("days", 1)))
        candidate = due + timedelta(days=days)
        if schedule_type == "MARKET_CALENDAR":
            while candidate.weekday() >= 5:
                candidate += timedelta(days=1)
        return candidate
    raise ValueError(f"unsupported schedule type: {definition.schedule_type}")


def claim_due_occurrences(
    session: Session,
    scheduler_id: str,
    *,
    now: datetime | None = None,
    lease_seconds: int = 60,
    limit: int = 100,
) -> list[ScheduledTaskOccurrence]:
    """Atomically materialize and lease each due occurrence at most once."""

    current = now or datetime.now(UTC)
    statement = (
        select(ScheduledTaskDefinition)
        .where(
            ScheduledTaskDefinition.enabled.is_(True),
            ScheduledTaskDefinition.next_due_at <= current,
        )
        .order_by(ScheduledTaskDefinition.next_due_at, ScheduledTaskDefinition.id)
        .limit(limit)
    )
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    definitions = session.scalars(statement).all()
    claimed: list[ScheduledTaskOccurrence] = []
    for definition in definitions:
        due = definition.next_due_at
        key = hashlib.sha256(f"{definition.id}:{due.isoformat()}".encode()).hexdigest()
        occurrence = ScheduledTaskOccurrence(
            definition_id=definition.id,
            workspace_id=definition.workspace_id,
            scheduled_for=due,
            status="QUEUED",
            idempotency_key=key,
            result_manifest={"scheduled_by": scheduler_id},
        )
        try:
            with session.begin_nested():
                session.add(occurrence)
                session.flush()
        except IntegrityError:
            continue
        definition.last_scheduled_at = due
        definition.next_due_at = next_due(definition, due)
        claimed.append(occurrence)
    session.flush()
    return claimed


def claim_next_occurrence(
    session: Session,
    worker_id: str,
    *,
    now: datetime | None = None,
    lease_seconds: int = 60,
) -> ScheduledTaskOccurrence | None:
    current = now or datetime.now(UTC)
    statement = (
        select(ScheduledTaskOccurrence)
        .where(
            or_(
                ScheduledTaskOccurrence.status == "QUEUED",
                (ScheduledTaskOccurrence.status == "RETRY_WAIT")
                & (ScheduledTaskOccurrence.next_retry_at <= current),
            )
        )
        .order_by(ScheduledTaskOccurrence.scheduled_for, ScheduledTaskOccurrence.id)
        .limit(1)
    )
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    occurrence = session.scalar(statement)
    if occurrence is None:
        return None
    occurrence.status = "CLAIMED"
    occurrence.claimed_by = worker_id
    occurrence.lease_expires_at = current + timedelta(seconds=lease_seconds)
    occurrence.attempts += 1
    occurrence.started_at = occurrence.started_at or current
    session.flush()
    return occurrence


def complete_occurrence(
    session: Session,
    occurrence: ScheduledTaskOccurrence,
    *,
    result_manifest: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> None:
    occurrence.status = "SUCCEEDED"
    occurrence.finished_at = now or datetime.now(UTC)
    occurrence.claimed_by = None
    occurrence.lease_expires_at = None
    occurrence.result_manifest = {**occurrence.result_manifest, **(result_manifest or {})}
    session.flush()


def fail_occurrence(
    session: Session,
    occurrence: ScheduledTaskOccurrence,
    *,
    error_category: str,
    sanitized_error: str,
    now: datetime | None = None,
    retry_after_seconds: int | None = None,
) -> None:
    current = now or datetime.now(UTC)
    definition = session.get(ScheduledTaskDefinition, occurrence.definition_id)
    maximum = int((definition.retry_policy if definition else {}).get("maximum_attempts", 3))
    retryable = error_category in RETRYABLE_CATEGORIES and occurrence.attempts < maximum
    occurrence.error_category = error_category
    occurrence.sanitized_error = sanitized_error[:1000]
    occurrence.claimed_by = None
    occurrence.lease_expires_at = None
    if retryable:
        occurrence.status = "RETRY_WAIT"
        occurrence.next_retry_at = current + compute_retry_delay(
            occurrence.attempts,
            retry_after_seconds=retry_after_seconds,
            jitter_seed=str(occurrence.id),
        )
    else:
        occurrence.status = "QUARANTINED"
        occurrence.finished_at = current
    session.flush()


def recover_expired_occurrences(
    session: Session, *, now: datetime | None = None
) -> list[ScheduledTaskOccurrence]:
    current = now or datetime.now(UTC)
    session.flush()
    rows = session.scalars(
        select(ScheduledTaskOccurrence).where(
            ScheduledTaskOccurrence.status.in_(("CLAIMED", "RUNNING")),
            ScheduledTaskOccurrence.lease_expires_at <= current,
        )
    ).all()
    for row in rows:
        definition = session.get(ScheduledTaskDefinition, row.definition_id)
        maximum = int((definition.retry_policy if definition else {}).get("maximum_attempts", 3))
        if row.attempts >= maximum:
            row.status = "QUARANTINED"
            row.finished_at = current
            row.error_category = row.error_category or "UNKNOWN"
        else:
            row.status = "RETRY_WAIT"
            row.next_retry_at = current + compute_retry_delay(row.attempts, jitter_seed=str(row.id))
        row.claimed_by = None
        row.lease_expires_at = None
        row.sanitized_error = "Worker lease expired; occurrence recovered"
    session.flush()
    return list(rows)


def calculate_freshness(
    *,
    now: datetime,
    last_success: datetime | None,
    expected_next: datetime | None,
    stale_after: datetime | None,
    market_calendar: bool = False,
    provider_delayed: bool = False,
    holidays: set[date] | None = None,
) -> str:
    if provider_delayed:
        return "PROVIDER_DELAYED"
    if last_success is None or expected_next is None or stale_after is None:
        return "UNKNOWN"
    effective_now = now
    if market_calendar:
        closed = holidays or set()
        probe = now.date()
        while probe.weekday() >= 5 or probe in closed:
            probe -= timedelta(days=1)
        if probe < now.date() and last_success.date() >= probe:
            return "CURRENT"
        if probe < now.date():
            effective_now = datetime.combine(probe, datetime.max.time(), tzinfo=UTC)
    if effective_now <= expected_next:
        return "CURRENT"
    if effective_now <= stale_after:
        return "DUE"
    very_stale_at = stale_after + max(stale_after - expected_next, timedelta(days=1))
    return "VERY_STALE" if effective_now > very_stale_at else "STALE"


def refresh_freshness(session: Session, *, now: datetime | None = None) -> int:
    current = now or datetime.now(UTC)
    rows = session.scalars(select(DataFreshnessStatus)).all()
    for row in rows:
        row.status = calculate_freshness(
            now=current,
            last_success=row.last_success_at,
            expected_next=row.expected_next_update_at,
            stale_after=row.stale_after_at,
            market_calendar=bool(row.calendar),
            provider_delayed=row.provider_delayed,
        )
        if row.status in {"STALE", "VERY_STALE"} and row.criticality == "CRITICAL":
            record_alert(
                session,
                workspace_id=row.workspace_id,
                severity="ERROR",
                category="STALE_CRITICAL_DATA",
                deduplication_key=f"freshness:{row.id}",
                summary=f"{row.provider} {row.dataset} is stale",
                impact="Research using this dataset may be delayed.",
                unaffected="The application and previously stored observations remain available.",
                recommended_action="Inspect the provider and the next scheduled ingestion attempt.",
                now=current,
            )
    session.flush()
    return len(rows)


def record_alert(
    session: Session,
    *,
    workspace_id: Any,
    severity: str,
    category: str,
    deduplication_key: str,
    summary: str,
    impact: str = "",
    unaffected: str = "",
    recommended_action: str = "",
    now: datetime | None = None,
) -> OperationalAlert:
    current = now or datetime.now(UTC)
    alert = session.scalar(
        select(OperationalAlert).where(
            OperationalAlert.workspace_id == workspace_id,
            OperationalAlert.deduplication_key == deduplication_key,
            OperationalAlert.status == "OPEN",
        )
    )
    if alert is None:
        alert = OperationalAlert(
            workspace_id=workspace_id,
            severity=severity,
            category=category,
            deduplication_key=deduplication_key,
            summary=summary,
            impact=impact,
            unaffected=unaffected,
            recommended_action=recommended_action,
            first_seen_at=current,
            last_seen_at=current,
        )
        session.add(alert)
    else:
        alert.occurrence_count += 1
        alert.last_seen_at = current
        alert.severity = severity
        alert.summary = summary
    session.flush()
    return alert


def dependency_status(
    *, database: bool, required_storage: bool, optional_provider: bool
) -> dict[str, str]:
    ready = database and required_storage
    return {
        "status": "HEALTHY"
        if ready and optional_provider
        else "DEGRADED"
        if ready
        else "ACTION_NEEDED",
        "readiness": "ready" if ready else "not_ready",
        "optional_providers": "healthy" if optional_provider else "degraded",
    }


def queue_age_seconds(session: Session, now: datetime | None = None) -> int:
    current = now or datetime.now(UTC)
    oldest = session.scalar(
        select(func.min(ScheduledTaskOccurrence.created_at)).where(
            or_(
                ScheduledTaskOccurrence.status == "QUEUED",
                ScheduledTaskOccurrence.status == "RETRY_WAIT",
            )
        )
    )
    return max(0, int((current - oldest).total_seconds())) if oldest else 0
