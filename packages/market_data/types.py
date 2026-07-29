from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

CAPABILITIES: tuple[str, ...] = (
    "historical_ohlcv",
    "corporate_actions",
    "asset_metadata",
    "exchange_calendars",
)


class ProviderError(RuntimeError):
    """Base error raised at the provider boundary."""


class ProviderDisabledError(ProviderError):
    """Raised when a disabled or unconfigured adapter is invoked."""


class ProviderTemporaryError(ProviderError):
    """Retryable provider failure such as throttling or temporary unavailability."""


class ProviderRateLimitError(ProviderTemporaryError):
    """Retryable provider throttling response."""


class ProviderResponseError(ProviderError):
    """Permanent malformed, empty, or unsupported provider response."""


@dataclass(frozen=True)
class HistoricalBarRecord:
    symbol: str
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
    adjustment_status: str = "unadjusted"
    version: int = 1
    checksum: str = ""
    provider_symbol: str = ""
    raw_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class CorporateActionRecord:
    symbol: str
    action_type: str
    effective_time: datetime
    publication_time: datetime
    retrieval_time: datetime
    ratio: Decimal | None = None
    amount: Decimal | None = None
    currency: str | None = None
    old_symbol: str | None = None
    new_symbol: str | None = None
    version: int = 1
    checksum: str = ""


@dataclass(frozen=True)
class AssetMetadataRecord:
    symbol: str
    name: str
    asset_type: str
    exchange: str
    currency: str
    sector: str | None
    industry: str | None
    effective_time: datetime
    retrieval_time: datetime
    metadata: dict[str, Any]
    version: int = 1
    checksum: str = ""


@dataclass(frozen=True)
class CalendarSessionRecord:
    calendar_code: str
    session_date: str
    open_time: datetime
    close_time: datetime
    is_early_close: bool = False


class HistoricalOHLCVProvider(Protocol):
    code: str

    def fetch_historical_bars(
        self, symbol: str, start: datetime, end: datetime, interval: str = "1d"
    ) -> list[HistoricalBarRecord]: ...


class CorporateActionsProvider(Protocol):
    code: str

    def fetch_corporate_actions(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[CorporateActionRecord]: ...


class AssetMetadataProvider(Protocol):
    code: str

    def fetch_asset_metadata(self, symbol: str) -> AssetMetadataRecord: ...


class ExchangeCalendarProvider(Protocol):
    code: str

    def fetch_exchange_calendar(
        self, exchange: str, start: datetime, end: datetime
    ) -> list[CalendarSessionRecord]: ...


class MarketDataAdapter(
    HistoricalOHLCVProvider,
    CorporateActionsProvider,
    AssetMetadataProvider,
    ExchangeCalendarProvider,
    Protocol,
):
    code: str
    name: str
    capabilities: tuple[str, ...]

    def health(self) -> dict[str, Any]: ...
