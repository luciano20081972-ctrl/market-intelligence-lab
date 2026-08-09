from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class JobClass(StrEnum):
    INTERACTIVE_LIGHT = "INTERACTIVE_LIGHT"
    STANDARD = "STANDARD"
    HEAVY = "HEAVY"
    VERY_HEAVY = "VERY_HEAVY"


class ComputeState(StrEnum):
    QUEUED = "QUEUED"
    ESTIMATING = "ESTIMATING"
    ROUTING = "ROUTING"
    LOCAL_RUNNING = "LOCAL_RUNNING"
    CLOUD_SUBMITTING = "CLOUD_SUBMITTING"
    CLOUD_QUEUED = "CLOUD_QUEUED"
    CLOUD_RUNNING = "CLOUD_RUNNING"
    CHECKPOINTED = "CHECKPOINTED"
    RESULT_VALIDATING = "RESULT_VALIDATING"
    SUCCEEDED = "SUCCEEDED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"
    CANCELED = "CANCELED"
    BLOCKED_BY_BUDGET = "BLOCKED_BY_BUDGET"
    WAITING_FOR_CAPACITY = "WAITING_FOR_CAPACITY"
    CLOUD_DISABLED = "CLOUD_DISABLED"


class ComputeProviderName(StrEnum):
    LOCAL = "local"
    GOOGLE_CLOUD_RUN_JOBS = "google_cloud_run_jobs"
    GOOGLE_BATCH = "google_batch"


class ErrorClassification(StrEnum):
    NONE = "NONE"
    TRANSIENT_PROVIDER = "TRANSIENT_PROVIDER"
    CAPACITY = "CAPACITY"
    BUDGET = "BUDGET"
    INVALID_INPUT = "INVALID_INPUT"
    INVALID_RESULT = "INVALID_RESULT"
    CANCELED = "CANCELED"
    INTERNAL = "INTERNAL"


TERMINAL_STATES = {
    ComputeState.SUCCEEDED,
    ComputeState.FAILED_FINAL,
    ComputeState.CANCELED,
}


@dataclass(frozen=True)
class ResourceEstimate:
    cpu: Decimal
    ram_mb: int
    runtime_seconds: int
    estimated_cost_usd: Decimal = Decimal("0")
    task_count: int = 1

    def __post_init__(self) -> None:
        if self.cpu <= 0 or self.ram_mb <= 0 or self.runtime_seconds <= 0:
            raise ValueError("resource estimates must be positive")
        if self.estimated_cost_usd < 0:
            raise ValueError("estimated cost cannot be negative")
        if self.task_count < 1 or self.task_count > 10_000:
            raise ValueError("task_count must be between 1 and 10000")


@dataclass(frozen=True)
class ComputeJobSpec:
    workspace_id: UUID
    requested_by: UUID
    submission_key: str
    job_type: str
    job_class: JobClass
    estimate: ResourceEstimate
    priority: int = 50
    deadline: datetime | None = None
    symbols: tuple[str, ...] = ()
    date_start: date | None = None
    date_end: date | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    strategy_version: str | None = None
    hypothesis_version: str | None = None
    model_version: str | None = None
    input_manifest: dict[str, Any] = field(default_factory=dict)
    input_manifest_hash: str = ""
    data_provenance: dict[str, Any] = field(default_factory=dict)
    data_version: str | None = None
    max_attempts: int = 3
    max_cost_usd: Decimal | None = None
    job_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.submission_key.strip() or len(self.submission_key) > 160:
            raise ValueError("submission_key must be nonblank and at most 160 characters")
        if not self.job_type.strip() or len(self.job_type) > 80:
            raise ValueError("job_type must be nonblank and at most 80 characters")
        if not 0 <= self.priority <= 100:
            raise ValueError("priority must be between 0 and 100")
        if not 1 <= self.max_attempts <= 10:
            raise ValueError("max_attempts must be between 1 and 10")
        if self.date_start and self.date_end and self.date_start > self.date_end:
            raise ValueError("date_start must not follow date_end")
        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError("symbols must be unique")
        if self.max_cost_usd is not None and self.max_cost_usd < 0:
            raise ValueError("max_cost_usd cannot be negative")
