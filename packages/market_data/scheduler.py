from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

QueueName = Literal["daily", "manual", "retry", "failed"]


@dataclass(frozen=True)
class ScheduledImport:
    job_id: UUID
    queue: QueueName
    run_at: datetime
    reason: str


@dataclass
class InMemoryImportScheduler:
    """Deterministic scheduler boundary; replaceable by a durable worker service later."""

    queues: dict[QueueName, list[ScheduledImport]] = field(
        default_factory=lambda: {"daily": [], "manual": [], "retry": [], "failed": []}
    )

    def enqueue(
        self,
        job_id: UUID,
        *,
        queue: QueueName = "manual",
        run_at: datetime | None = None,
        reason: str = "requested",
    ) -> ScheduledImport:
        item = ScheduledImport(job_id, queue, run_at or datetime.now(UTC), reason)
        if any(existing.job_id == job_id for existing in self.queues[queue]):
            return next(existing for existing in self.queues[queue] if existing.job_id == job_id)
        self.queues[queue].append(item)
        self.queues[queue].sort(key=lambda value: value.run_at)
        return item

    def dequeue_ready(self, queue: QueueName, now: datetime | None = None) -> list[ScheduledImport]:
        cutoff = now or datetime.now(UTC)
        ready = [item for item in self.queues[queue] if item.run_at <= cutoff]
        self.queues[queue] = [item for item in self.queues[queue] if item.run_at > cutoff]
        return ready
