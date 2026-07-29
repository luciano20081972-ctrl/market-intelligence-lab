from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator


class ImportPreviewRequest(BaseModel):
    provider_code: str = Field(min_length=1, max_length=48)
    symbols: list[str] = Field(min_length=1, max_length=25)
    start: datetime
    end: datetime
    mode: Literal["full", "incremental"] = "incremental"
    adjustment_preference: Literal["adjusted", "unadjusted", "provider_default"] = (
        "provider_default"
    )
    dry_run: bool = True

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().upper() for item in value]
        if len(set(normalized)) != len(normalized) or any(not item for item in normalized):
            raise ValueError("symbols must be nonblank and unique")
        return normalized

    @model_validator(mode="after")
    def validate_range(self) -> ImportPreviewRequest:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("start and end must include a timezone")
        if self.start >= self.end:
            raise ValueError("start must be before end")
        if (self.end - self.start).days > 7400:
            raise ValueError("date range cannot exceed 7400 days")
        return self


class ScheduleCreate(BaseModel):
    provider_id: UUID
    name: str = Field(min_length=1, max_length=120)
    symbols: list[str] = Field(min_length=1, max_length=100)
    mode: Literal["full", "incremental"] = "incremental"
    adjustment_preference: Literal["adjusted", "unadjusted", "provider_default"] = (
        "provider_default"
    )
    timezone: str = Field(default="UTC", min_length=1, max_length=80)
    next_run_at: datetime
    lookback_days: int = Field(default=7, ge=1, le=7400)
    is_enabled: bool = True

    @field_validator("symbols")
    @classmethod
    def normalize_schedule_symbols(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().upper() for item in value]
        if any(not item for item in normalized) or len(set(normalized)) != len(normalized):
            raise ValueError("symbols must be nonblank and unique")
        return normalized

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

    @field_validator("next_run_at")
    @classmethod
    def validate_next_run(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("next_run_at must include a timezone")
        return value


class ScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_enabled: bool | None = None
    next_run_at: datetime | None = None
    lookback_days: int | None = Field(default=None, ge=1, le=7400)


class ReconciliationRequest(BaseModel):
    provider_id: UUID | None = None
    symbols: list[str] = Field(default_factory=list, max_length=100)
    dry_run: bool = True
