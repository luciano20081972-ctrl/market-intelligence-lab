from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class ProviderResponse(BaseModel):
    id: UUID
    code: str
    name: str
    capabilities: list[str]
    credential_environment_keys: list[str]
    is_enabled: bool
    health: str
    last_tested_at: datetime | None
    last_successful_import_at: datetime | None
    adapter_type: str = ""
    authentication_required: bool = False
    configuration_status: str = "unconfigured"


class ProviderPage(BaseModel):
    items: list[ProviderResponse]
    meta: PageMeta


class ProviderTestRequest(BaseModel):
    provider_id: UUID


class ProviderTestResponse(BaseModel):
    provider_id: UUID
    status: str
    checked_at: datetime
    details: dict[str, Any]


class ImportJobCreate(BaseModel):
    provider_code: str = Field(min_length=1, max_length=48)
    symbols: list[str] = Field(min_length=1, max_length=25)
    mode: Literal["full", "incremental"] = "incremental"
    start: datetime
    end: datetime
    interval: str = Field(default="1d", pattern=r"^(1d|1h|15m|5m|1m)$")
    max_attempts: int = Field(default=3, ge=1, le=10)
    execute_immediately: bool = False
    adjustment_preference: Literal["adjusted", "unadjusted", "provider_default"] = (
        "provider_default"
    )
    dry_run: bool = False

    @field_validator("symbols")
    @classmethod
    def unique_symbols(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().upper() for item in value]
        if len(set(normalized)) != len(normalized):
            raise ValueError("symbols must not contain duplicates")
        return normalized


class ImportBatchResponse(BaseModel):
    id: UUID
    sequence: int
    status: str
    records_processed: int
    records_inserted: int
    records_skipped: int
    checksum: str
    validation_report: dict[str, Any]


class ImportJobResponse(BaseModel):
    id: UUID
    provider_id: UUID
    provider_code: str
    mode: str
    status: str
    symbols: list[str]
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    next_retry_at: datetime | None
    attempt: int
    max_attempts: int
    records_processed: int
    records_inserted: int
    records_skipped: int
    processing_duration_ms: int
    error_summary: str | None
    validation_report: dict[str, Any]
    resume_cursor: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False
    adjustment_preference: str = "provider_default"
    queue_name: str = "manual"
    batches: list[ImportBatchResponse] = Field(default_factory=list)


class ImportJobPage(BaseModel):
    items: list[ImportJobResponse]
    meta: PageMeta


class ImportErrorResponse(BaseModel):
    id: UUID
    job_id: UUID
    batch_id: UUID | None
    error_code: str
    message: str
    record_identifier: str | None
    is_retryable: bool
    occurred_at: datetime


class ImportErrorPage(BaseModel):
    items: list[ImportErrorResponse]
    meta: PageMeta


class CorporateActionResponse(BaseModel):
    id: UUID
    symbol: str
    provider_code: str
    action_type: str
    effective_time: datetime
    publication_time: datetime
    ratio: str | None
    amount: str | None
    currency: str | None
    old_symbol: str | None
    new_symbol: str | None
    adjustment_status: str


class CorporateActionPage(BaseModel):
    items: list[CorporateActionResponse]
    meta: PageMeta


class TradingSessionResponse(BaseModel):
    id: UUID
    calendar_code: str
    timezone: str
    session_date: str
    open_time: datetime
    close_time: datetime
    is_early_close: bool
    status: str


class TradingSessionPage(BaseModel):
    items: list[TradingSessionResponse]
    meta: PageMeta
