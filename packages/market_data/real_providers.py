from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from packages.market_data.rate_limit import InProcessRateLimiter
from packages.market_data.types import (
    AssetMetadataRecord,
    CalendarSessionRecord,
    CorporateActionRecord,
    HistoricalBarRecord,
    ProviderAccessDeniedError,
    ProviderContentTypeError,
    ProviderDataError,
    ProviderDisabledError,
    ProviderHtmlResponseError,
    ProviderInvalidDateRangeError,
    ProviderNetworkError,
    ProviderNoDataError,
    ProviderRateLimitError,
    ProviderRejectedRequestError,
    ProviderResponseTooLargeError,
    ProviderSchemaError,
    ProviderTemporaryError,
    ProviderUnsupportedSymbolError,
)


def _symbol(value: str) -> str:
    normalized = value.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,30}", normalized):
        raise ProviderUnsupportedSymbolError("Unsupported U.S. security symbol format")
    return normalized


class _JsonProvider:
    max_response_bytes = 8_000_000
    allowed_host: str
    code: str

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 15,
        requests_per_minute: int,
    ) -> None:
        if not 1 <= timeout_seconds <= 60:
            raise ValueError("Provider timeout must be between 1 and 60 seconds")
        if requests_per_minute < 1:
            raise ValueError("Provider request entitlement must be positive")
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self.rate_limiter = InProcessRateLimiter(requests_per_minute, 60)

    def _request(
        self,
        url: str,
        *,
        params: dict[str, str],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not self.rate_limiter.allow(self.allowed_host):
            raise ProviderRateLimitError("Configured provider request entitlement is exhausted")
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=httpx.Timeout(self.timeout_seconds),
                follow_redirects=False,
                headers=headers,
            ) as client:
                response = client.get(url, params=params)
        except httpx.RequestError as exc:
            raise ProviderNetworkError("Market provider was unavailable") from exc
        if response.url.scheme != "https" or response.url.host != self.allowed_host:
            raise ProviderAccessDeniedError("Provider returned an unexpected response location")
        if len(response.content) > self.max_response_bytes:
            raise ProviderResponseTooLargeError("Provider response exceeded the size limit")
        if response.status_code == 429:
            raise ProviderRateLimitError("Provider rate limit reached; retry later")
        if response.status_code in {401, 403}:
            raise ProviderAccessDeniedError(
                "Provider rejected configured credentials or entitlement"
            )
        if response.status_code >= 500:
            raise ProviderTemporaryError("Provider is temporarily unavailable")
        if response.status_code != 200:
            raise ProviderRejectedRequestError("Provider rejected the bounded request")
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type not in {"", "application/json", "text/json"}:
            raise ProviderContentTypeError("Provider returned an unexpected content type")
        if response.content.lstrip().lower().startswith((b"<!doctype html", b"<html")):
            raise ProviderHtmlResponseError("Provider returned HTML instead of market data")
        try:
            result = response.json()
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderSchemaError("Provider returned malformed JSON") from exc
        if not isinstance(result, dict):
            raise ProviderSchemaError("Provider response root was not an object")
        return result

    @staticmethod
    def _bars(
        rows: object,
        *,
        symbol: str,
        provider_symbol: str,
        timestamp_key: str,
        millisecond_timestamps: bool,
        metadata: dict[str, Any],
    ) -> list[HistoricalBarRecord]:
        if not isinstance(rows, list):
            raise ProviderSchemaError("Provider response omitted the bars array")
        retrieved = datetime.now(UTC)
        records: list[HistoricalBarRecord] = []
        for row in rows:
            if not isinstance(row, dict):
                raise ProviderSchemaError("Provider returned a malformed bar")
            try:
                raw_time = row[timestamp_key]
                if millisecond_timestamps:
                    event_time = datetime.fromtimestamp(int(raw_time) / 1000, UTC)
                else:
                    event_time = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
                prices = {
                    key: Decimal(str(row[key]))
                    for key in ("o", "h", "l", "c")
                }
                volume = int(row["v"])
            except (KeyError, ValueError, TypeError, InvalidOperation) as exc:
                raise ProviderDataError("Provider bar contained an invalid value") from exc
            if event_time.tzinfo is None:
                raise ProviderDataError("Provider bar timestamp omitted timezone")
            if any(not price.is_finite() or price <= 0 for price in prices.values()):
                raise ProviderDataError("Provider bar contained a non-positive price")
            if prices["h"] < max(prices["o"], prices["c"]) or prices["l"] > min(
                prices["o"], prices["c"]
            ):
                raise ProviderDataError("Provider bar contained inconsistent OHLC values")
            if volume < 0:
                raise ProviderDataError("Provider bar contained invalid volume")
            checksum = hashlib.sha256(
                json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            records.append(
                HistoricalBarRecord(
                    symbol=symbol,
                    interval="1d",
                    event_time=event_time.astimezone(UTC),
                    publication_time=retrieved,
                    effective_time=event_time.astimezone(UTC),
                    retrieval_time=retrieved,
                    open=prices["o"],
                    high=prices["h"],
                    low=prices["l"],
                    close=prices["c"],
                    adjusted_close=prices["c"],
                    volume=volume,
                    adjustment_status="provider_adjusted",
                    checksum=checksum,
                    provider_symbol=provider_symbol,
                    raw_metadata=metadata,
                )
            )
        if not records:
            raise ProviderNoDataError("Provider returned no bars for the bounded request")
        return sorted(records, key=lambda item: item.event_time)

    def fetch_corporate_actions(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[CorporateActionRecord]:
        del symbol, start, end
        return []

    def fetch_asset_metadata(self, symbol: str) -> AssetMetadataRecord:
        canonical = _symbol(symbol)
        now = datetime.now(UTC)
        return AssetMetadataRecord(
            symbol=canonical,
            name=canonical,
            asset_type="equity",
            exchange="US",
            currency="USD",
            sector=None,
            industry=None,
            effective_time=now,
            retrieval_time=now,
            metadata={"status": "symbol_only", "provider": self.code},
        )

    def fetch_exchange_calendar(
        self, exchange: str, start: datetime, end: datetime
    ) -> list[CalendarSessionRecord]:
        del exchange, start, end
        return []


class MassiveBasicAdapter(_JsonProvider):
    """Massive Basic daily adapter; plan capabilities remain runtime configuration."""

    code = "massive"
    name = "Massive Basic"
    capabilities: tuple[str, ...] = (
        "historical_ohlcv",
        "asset_metadata",
        "corporate_actions",
    )
    base_url = "https://api.massive.com"
    allowed_host = "api.massive.com"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 15,
        requests_per_minute: int | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("MIL_MASSIVE_API_KEY")
        limit = requests_per_minute or int(os.getenv("MIL_MASSIVE_REQUESTS_PER_MINUTE", "5"))
        super().__init__(
            transport=transport,
            timeout_seconds=timeout_seconds,
            requests_per_minute=limit,
        )

    def health(self) -> dict[str, Any]:
        return {
            "status": "unknown" if self._api_key else "unconfigured",
            "configured": bool(self._api_key),
            "provider": self.code,
            "feed": "END_OF_DAY",
            "live_verified": False,
        }

    def fetch_historical_bars(
        self, symbol: str, start: datetime, end: datetime, interval: str = "1d"
    ) -> list[HistoricalBarRecord]:
        if not self._api_key:
            raise ProviderDisabledError("Massive credentials are not configured")
        if interval != "1d" or start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ProviderInvalidDateRangeError("Massive requires an ordered daily UTC range")
        canonical = _symbol(symbol)
        root = self._request(
            f"{self.base_url}/v2/aggs/ticker/{canonical}/range/1/day/"
            f"{start.date().isoformat()}/{end.date().isoformat()}",
            params={"adjusted": "true", "sort": "asc", "limit": "50000", "apiKey": self._api_key},
        )
        return self._bars(
            root.get("results"),
            symbol=canonical,
            provider_symbol=canonical,
            timestamp_key="t",
            millisecond_timestamps=True,
            metadata={"provider": self.code, "feed": "END_OF_DAY", "adjusted": True},
        )

    def fetch_grouped_daily(self, session_date: datetime) -> dict[str, Any]:
        """One market-day request for entitlement-aware broad ingestion."""
        if not self._api_key:
            raise ProviderDisabledError("Massive credentials are not configured")
        return self._request(
            f"{self.base_url}/v2/aggs/grouped/locale/us/market/stocks/"
            f"{session_date.date().isoformat()}",
            params={"adjusted": "true", "apiKey": self._api_key},
        )


class AlpacaBasicAdapter(_JsonProvider):
    """Alpaca Basic historical adapter with explicit IEX realtime semantics."""

    code = "alpaca"
    name = "Alpaca Basic"
    capabilities: tuple[str, ...] = ("historical_ohlcv", "asset_metadata")
    base_url = "https://data.alpaca.markets"
    allowed_host = "data.alpaca.markets"

    def __init__(
        self,
        key_id: str | None = None,
        secret_key: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 15,
        requests_per_minute: int | None = None,
        realtime_capacity: int | None = None,
    ) -> None:
        self._key_id = key_id or os.getenv("MIL_ALPACA_API_KEY_ID")
        self._secret_key = secret_key or os.getenv("MIL_ALPACA_API_SECRET")
        limit = requests_per_minute or int(os.getenv("MIL_ALPACA_REQUESTS_PER_MINUTE", "200"))
        self.realtime_capacity = realtime_capacity or int(
            os.getenv("MIL_ALPACA_REALTIME_CAPACITY", "30")
        )
        if self.realtime_capacity < 0:
            raise ValueError("Alpaca realtime capacity cannot be negative")
        super().__init__(
            transport=transport,
            timeout_seconds=timeout_seconds,
            requests_per_minute=limit,
        )

    @property
    def configured(self) -> bool:
        return bool(self._key_id and self._secret_key)

    def health(self) -> dict[str, Any]:
        return {
            "status": "unknown" if self.configured else "unconfigured",
            "configured": self.configured,
            "provider": self.code,
            "realtime_feed": "LIVE — IEX",
            "realtime_capacity": self.realtime_capacity,
            "live_verified": False,
        }

    def fetch_historical_bars(
        self, symbol: str, start: datetime, end: datetime, interval: str = "1d"
    ) -> list[HistoricalBarRecord]:
        if not self.configured:
            raise ProviderDisabledError("Alpaca credentials are not configured")
        if interval != "1d" or start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ProviderInvalidDateRangeError("Alpaca requires an ordered daily UTC range")
        canonical = _symbol(symbol)
        root = self._request(
            f"{self.base_url}/v2/stocks/{canonical}/bars",
            params={
                "timeframe": "1Day",
                "start": start.astimezone(UTC).isoformat(),
                "end": end.astimezone(UTC).isoformat(),
                "adjustment": "all",
                "feed": "iex",
                "limit": "10000",
            },
            headers={
                "APCA-API-KEY-ID": str(self._key_id),
                "APCA-API-SECRET-KEY": str(self._secret_key),
            },
        )
        return self._bars(
            root.get("bars"),
            symbol=canonical,
            provider_symbol=canonical,
            timestamp_key="t",
            millisecond_timestamps=False,
            metadata={"provider": self.code, "feed": "IEX", "label": "LIVE — IEX"},
        )
