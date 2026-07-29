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
    """Base safe error raised at the provider boundary."""

    classification = "provider_error"
    reachable = False


class ProviderDisabledError(ProviderError):
    """Raised when a disabled or unconfigured adapter is invoked."""


class ProviderTemporaryError(ProviderError):
    """Retryable provider failure such as throttling or temporary unavailability."""

    classification = "provider_unavailable"
    reachable = True


class ProviderNetworkError(ProviderTemporaryError):
    """Raised when the provider cannot be reached at all."""

    classification = "network_unavailable"
    reachable = False


class ProviderRateLimitError(ProviderTemporaryError):
    """Retryable provider throttling response."""

    classification = "rate_limited"
    reachable = True


class ProviderResponseError(ProviderError):
    """Permanent malformed, empty, or unsupported provider response."""

    classification = "malformed_response"
    reachable = True


class ProviderContentTypeError(ProviderResponseError):
    """Raised when a reachable provider returns an unsupported media type."""

    classification = "unexpected_content_type"


class ProviderAccessDeniedError(ProviderResponseError):
    """Raised for a reachable provider access-denied response."""

    classification = "access_denied"


class ProviderRejectedRequestError(ProviderResponseError):
    """Raised when the provider rejects a bounded request."""

    classification = "provider_rejected_request"


class ProviderEncodingError(ProviderResponseError):
    """Raised when the response is not supported UTF-8/ASCII-compatible data."""

    classification = "unsupported_encoding"


class ProviderHtmlResponseError(ProviderResponseError):
    """Raised for HTML verification, access-denied, or error pages."""

    classification = "html_access_page"


class ProviderNoDataError(ProviderResponseError):
    """Raised when a valid provider response contains no observations."""

    classification = "no_data"


class ProviderUnsupportedSymbolError(ProviderResponseError):
    """Raised when a provider explicitly rejects the normalized symbol."""

    classification = "unsupported_symbol"


class ProviderInvalidDateRangeError(ProviderError):
    """Raised before a request when the requested date range is invalid."""

    classification = "invalid_date_range"


class ProviderSchemaError(ProviderResponseError):
    """Raised when a provider response does not match the required schema."""

    classification = "schema_mismatch"


class ProviderDataError(ProviderResponseError):
    """Raised when provider rows contain invalid dates or market values."""

    classification = "malformed_market_data"


class ProviderResponseTooLargeError(ProviderResponseError):
    """Raised when a provider response exceeds the safe byte limit."""

    classification = "response_too_large"


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
