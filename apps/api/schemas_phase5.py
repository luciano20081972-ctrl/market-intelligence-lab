from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator

from packages.compute.types import JobClass


class ResourceEstimateRequest(BaseModel):
    cpu: Decimal = Field(gt=0, le=64)
    ram_mb: int = Field(gt=0, le=262_144)
    runtime_seconds: int = Field(gt=0, le=604_800)
    estimated_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    task_count: int = Field(default=1, ge=1, le=10_000)


class ComputeJobCreate(BaseModel):
    submission_key: str = Field(min_length=1, max_length=160)
    job_type: str = Field(min_length=1, max_length=80)
    job_class: JobClass
    estimate: ResourceEstimateRequest
    priority: int = Field(default=50, ge=0, le=100)
    deadline: datetime | None = None
    symbols: list[str] = Field(default_factory=list, max_length=500)
    date_start: date | None = None
    date_end: date | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    strategy_version: str | None = Field(default=None, max_length=160)
    hypothesis_version: str | None = Field(default=None, max_length=160)
    model_version: str | None = Field(default=None, max_length=160)
    input_manifest: dict[str, Any] = Field(default_factory=dict)
    input_manifest_hash: str = Field(default="", max_length=64)
    data_provenance: dict[str, Any] = Field(default_factory=dict)
    data_version: str | None = Field(default=None, max_length=160)
    max_attempts: int = Field(default=3, ge=1, le=10)
    max_cost_usd: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_range_and_symbols(self) -> ComputeJobCreate:
        if self.date_start and self.date_end and self.date_start > self.date_end:
            raise ValueError("date_start must not follow date_end")
        normalized = [item.strip().upper() for item in self.symbols]
        if any(not item for item in normalized) or len(normalized) != len(set(normalized)):
            raise ValueError("symbols must be nonblank and unique")
        self.symbols = normalized
        return self


class ComputeRetryRequest(BaseModel):
    confirm_no_cloud_execution: bool = False
