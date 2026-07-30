from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str


class PageInfo(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int


class AssetSummary(BaseModel):
    id: UUID
    symbol: str
    name: str
    asset_type: str
    exchange: str
    currency: str
    sector: str | None
    industry: str | None
    is_active: bool
    latest_price: Decimal | None = None
    latest_price_time: datetime | None = None
    is_demonstration_data: bool | None = None


class AssetPage(BaseModel):
    items: list[AssetSummary]
    pagination: PageInfo


class PriceBarResponse(BaseModel):
    id: UUID
    interval: str
    event_time: datetime
    publication_time: datetime
    effective_time: datetime
    retrieval_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal
    volume: int
    data_source_id: UUID
    source_name: str
    is_demonstration_data: bool


class PricePage(BaseModel):
    symbol: str
    items: list[PriceBarResponse]
    pagination: PageInfo


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value


class WatchlistUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value


class WatchlistAssetCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=16, pattern=r"^[A-Za-z][A-Za-z0-9.\-]*$")

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, value: str) -> str:
        return value.strip().upper()


class WatchlistAssetResponse(BaseModel):
    symbol: str
    name: str
    added_at: datetime
    latest_price: Decimal | None
    latest_price_time: datetime | None
    is_demonstration_data: bool | None


class WatchlistResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    assets: list[WatchlistAssetResponse]


class DataSourceResponse(BaseModel):
    id: UUID
    name: str
    provider_type: str
    is_enabled: bool
    health: str
    last_successful_retrieval: datetime | None
    stored_records: int
    freshness_status: str
    license_notes: str


class SystemInfoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_name: str
    version: str
    environment: str
    database_engine: str
    demonstration_mode: bool
    authentication_mode: str
    database_health: str
    tracked_assets: int
    watchlists: int
    demonstration_bars: int
    warning: str
