from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import httpx

from packages.market_data.types import (
    CAPABILITIES,
    AssetMetadataRecord,
    CalendarSessionRecord,
    CorporateActionRecord,
    HistoricalBarRecord,
    ProviderAccessDeniedError,
    ProviderContentTypeError,
    ProviderDataError,
    ProviderDisabledError,
    ProviderEncodingError,
    ProviderError,
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

PROVIDER_DEFINITIONS: tuple[dict[str, object], ...] = (
    {"code": "alpha_vantage", "name": "Alpha Vantage", "env": ["ALPHA_VANTAGE_API_KEY"]},
    {"code": "twelve_data", "name": "Twelve Data", "env": ["TWELVE_DATA_API_KEY"]},
    {"code": "polygon", "name": "Polygon", "env": ["POLYGON_API_KEY"]},
    {"code": "financial_modeling_prep", "name": "Financial Modeling Prep", "env": ["FMP_API_KEY"]},
    {"code": "tiingo", "name": "Tiingo", "env": ["TIINGO_API_KEY"]},
    {"code": "stooq", "name": "Stooq", "env": []},
    {"code": "yahoo_finance", "name": "Yahoo Finance", "env": []},
)


class DisabledProviderAdapter:
    """Safe placeholder that performs no network calls until explicitly implemented."""

    capabilities: tuple[str, ...] = CAPABILITIES

    def __init__(self, code: str, name: str) -> None:
        self.code = code
        self.name = name

    def health(self) -> dict[str, object]:
        return {
            "status": "disabled",
            "provider": self.code,
            "network_called": False,
            "message": "Adapter placeholder is disabled; no external request was made.",
        }

    def _disabled(self) -> ProviderDisabledError:
        return ProviderDisabledError(
            f"Provider '{self.code}' is disabled until an adapter and configuration are enabled."
        )

    def fetch_historical_bars(
        self, symbol: str, start: datetime, end: datetime, interval: str = "1d"
    ) -> list[HistoricalBarRecord]:
        raise self._disabled()

    def fetch_corporate_actions(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[CorporateActionRecord]:
        raise self._disabled()

    def fetch_asset_metadata(self, symbol: str) -> AssetMetadataRecord:
        raise self._disabled()

    def fetch_exchange_calendar(
        self, exchange: str, start: datetime, end: datetime
    ) -> list[CalendarSessionRecord]:
        raise self._disabled()


@dataclass(frozen=True)
class StooqPayload:
    body: bytes
    content_type: str


class StooqAdapter:
    """Read-only daily OHLCV adapter for Stooq's fixed HTTPS CSV endpoint."""

    code = "stooq"
    name = "Stooq Historical Daily Data"
    capabilities: tuple[str, ...] = ("historical_ohlcv", "asset_metadata")
    base_url = "https://stooq.com/q/d/l/"
    max_response_bytes = 2_000_000
    max_range_days = 7_400

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.transport = transport
        configured_timeout = timeout_seconds or float(os.getenv("MIL_STOOQ_TIMEOUT_SECONDS", "10"))
        if configured_timeout < 1 or configured_timeout > 60:
            raise ValueError("Stooq timeout must be between 1 and 60 seconds")
        self.timeout_seconds = configured_timeout

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        canonical = symbol.strip().upper()
        if canonical.endswith(".US"):
            canonical = canonical[:-3]
        if not re.fullmatch(r"[A-Z][A-Z0-9-]{0,15}", canonical):
            raise ProviderUnsupportedSymbolError(
                "Stooq supports simple U.S. stock and ETF symbols in this adapter"
            )
        return f"{canonical.lower()}.us"

    @classmethod
    def request_parameters(
        cls, symbol: str, start: datetime, end: datetime, interval: str = "1d"
    ) -> dict[str, str]:
        if interval != "1d":
            raise ValueError("Stooq adapter supports daily bars only")
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ProviderInvalidDateRangeError(
                "Stooq start/end dates must be timezone-aware and ordered"
            )
        if (end - start).days > cls.max_range_days:
            raise ProviderInvalidDateRangeError(
                f"Stooq date range cannot exceed {cls.max_range_days} days"
            )
        return {
            "s": cls.normalize_symbol(symbol),
            "d1": start.strftime("%Y%m%d"),
            "d2": end.strftime("%Y%m%d"),
            "i": "d",
        }

    def health(self) -> dict[str, object]:
        return {
            "status": "unknown",
            "configured": True,
            "connectivity": "not_tested",
            "provider": self.code,
            "authentication_required": False,
            "base_url": self.base_url,
        }

    def test_connectivity(self) -> dict[str, object]:
        tested_at = datetime.now(UTC)
        start = datetime(2024, 1, 2, tzinfo=UTC)
        end = datetime(2024, 1, 10, 23, 59, tzinfo=UTC)
        try:
            records = self.fetch_historical_bars("AAPL", start, end)
        except ProviderError as exc:
            reachable = bool(exc.reachable)
            classification = exc.classification
            no_data = classification == "no_data"
            return {
                **self.health(),
                "status": "degraded" if reachable else "unavailable",
                "connectivity": ("reachable_no_data" if no_data else "reachable_invalid")
                if reachable
                else "unavailable",
                "reachable": reachable,
                "valid_response": False,
                "schema_compatible": no_data,
                "data_available": False,
                "degraded": reachable,
                "unavailable": not reachable,
                "response_classification": classification,
                "message": str(exc),
                "tested_at": tested_at.isoformat(),
            }
        return {
            **self.health(),
            "status": "healthy",
            "connectivity": "connected",
            "reachable": True,
            "valid_response": True,
            "schema_compatible": True,
            "data_available": bool(records),
            "degraded": False,
            "unavailable": False,
            "response_classification": "valid_csv",
            "message": "Stooq returned compatible daily OHLCV data",
            "tested_at": tested_at.isoformat(),
        }

    def _get(self, params: dict[str, str]) -> StooqPayload:
        try:
            with httpx.Client(
                timeout=httpx.Timeout(self.timeout_seconds),
                transport=self.transport,
                follow_redirects=False,
                headers={"User-Agent": "Market-Intelligence-Lab/0.10.0"},
            ) as client:
                response = client.get(self.base_url, params=params)
        except httpx.RequestError as exc:
            raise ProviderNetworkError("Stooq request timed out or could not be reached") from exc
        if response.url.scheme != "https" or response.url.host != "stooq.com":
            raise ProviderAccessDeniedError("Stooq returned an unexpected response location")
        body = response.content
        if len(body) > self.max_response_bytes:
            raise ProviderResponseTooLargeError("Stooq response exceeded the configured size limit")
        if response.status_code == 429:
            raise ProviderRateLimitError("Stooq rate limit reached; retry later")
        if response.status_code >= 500:
            raise ProviderTemporaryError(f"Stooq temporarily returned HTTP {response.status_code}")
        if response.status_code != 200:
            raise ProviderRejectedRequestError(
                f"Stooq rejected the bounded request with HTTP {response.status_code}"
            )
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        self._validate_response_envelope(body, content_type)
        return StooqPayload(body=body, content_type=content_type)

    @staticmethod
    def _decode(body: bytes) -> str:
        try:
            return body.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ProviderEncodingError(
                "Stooq returned data in an unsupported character encoding"
            ) from exc

    @classmethod
    def _validate_response_envelope(cls, body: bytes, content_type: str) -> None:
        if not body.strip():
            raise ProviderNoDataError("Stooq returned no data for the bounded request")
        text = cls._decode(body)
        normalized = text.strip().lower()
        html_prefixes = ("<!doctype html", "<html", "<head", "<body")
        if content_type in {"text/html", "application/xhtml+xml"} or normalized.startswith(
            html_prefixes
        ):
            raise ProviderHtmlResponseError(
                "Stooq returned an HTML verification or access page instead of market data"
            )
        known_responses: dict[str, type[ProviderError]] = {
            "no data": ProviderNoDataError,
            "no data.": ProviderNoDataError,
            "symbol not found": ProviderUnsupportedSymbolError,
            "invalid symbol": ProviderUnsupportedSymbolError,
            "unsupported symbol": ProviderUnsupportedSymbolError,
            "access denied": ProviderAccessDeniedError,
            "forbidden": ProviderAccessDeniedError,
            "rate limit exceeded": ProviderRateLimitError,
            "too many requests": ProviderRateLimitError,
        }
        error_type = known_responses.get(normalized)
        if error_type is not None:
            safe_label = normalized.removesuffix(".")
            raise error_type(f"Stooq reported: {safe_label}")
        allowed_content_types = {
            "",
            "application/csv",
            "application/octet-stream",
            "application/vnd.ms-excel",
            "text/csv",
            "text/plain",
        }
        if content_type not in allowed_content_types:
            raise ProviderContentTypeError(
                "Stooq returned an unsupported content type instead of CSV market data"
            )

    @classmethod
    def _parse_csv(
        cls,
        payload: StooqPayload,
        symbol: str,
        provider_symbol: str,
        start: datetime,
        end: datetime,
    ) -> list[HistoricalBarRecord]:
        text = cls._decode(payload.body)
        first_line = next((line for line in text.splitlines() if line.strip()), "")
        if ";" in first_line and "," not in first_line:
            raise ProviderSchemaError("Stooq CSV used an unsupported delimiter")
        try:
            parsed_rows = [
                row
                for row in csv.reader(io.StringIO(text, newline=""), strict=True)
                if any(cell.strip() for cell in row)
            ]
        except csv.Error as exc:
            raise ProviderSchemaError("Stooq CSV syntax was malformed") from exc
        if not parsed_rows:
            raise ProviderNoDataError("Stooq returned no data for the bounded request")

        required = ("date", "open", "high", "low", "close", "volume")
        header = tuple(cell.strip().lower() for cell in parsed_rows[0])
        if len(header) != len(set(header)):
            raise ProviderSchemaError("Stooq CSV contained duplicate columns")
        if len(header) != len(required) or set(header) != set(required):
            raise ProviderSchemaError("Stooq CSV columns were missing or malformed")
        positions = {name: header.index(name) for name in required}

        retrieved = datetime.now(UTC)
        timezone = ZoneInfo("America/New_York")
        canonical_symbol = symbol.strip().upper().removesuffix(".US")
        records: list[HistoricalBarRecord] = []
        seen_dates: set[object] = set()
        for row in parsed_rows[1:]:
            if len(row) != len(header):
                raise ProviderSchemaError("Stooq CSV row did not match the declared schema")
            values = {name: row[index].strip() for name, index in positions.items()}
            if any(value == "" or value.upper() == "N/D" for value in values.values()):
                raise ProviderDataError("Stooq CSV contained a missing market value")
            date_text = values["date"]
            try:
                session_date = datetime.strptime(date_text, "%Y-%m-%d").date()
            except ValueError as exc:
                raise ProviderDataError("Stooq CSV contained an invalid market date") from exc
            if date_text != session_date.isoformat():
                raise ProviderDataError("Stooq CSV contained a non-canonical market date")
            if session_date < start.date() or session_date > end.date():
                raise ProviderDataError("Stooq CSV contained a date outside the bounded request")
            if session_date in seen_dates:
                raise ProviderDataError("Stooq CSV contained a duplicate market date")
            seen_dates.add(session_date)

            prices: dict[str, Decimal] = {}
            for field in ("open", "high", "low", "close"):
                try:
                    value = Decimal(values[field])
                except InvalidOperation as exc:
                    raise ProviderDataError("Stooq CSV contained an invalid market value") from exc
                if not value.is_finite() or value <= 0:
                    raise ProviderDataError("Stooq CSV contained an invalid market value")
                prices[field] = value
            try:
                volume_decimal = Decimal(values["volume"])
            except InvalidOperation as exc:
                raise ProviderDataError("Stooq CSV contained an invalid volume") from exc
            if (
                not volume_decimal.is_finite()
                or volume_decimal < 0
                or volume_decimal != volume_decimal.to_integral_value()
            ):
                raise ProviderDataError("Stooq CSV contained an invalid volume")
            if (
                prices["high"] < max(prices["open"], prices["close"])
                or prices["low"] > min(prices["open"], prices["close"])
                or prices["low"] > prices["high"]
            ):
                raise ProviderDataError("Stooq CSV contained inconsistent OHLC values")

            close_local = datetime.combine(
                session_date, datetime.min.time(), tzinfo=timezone
            ) + timedelta(hours=16)
            event_time = close_local.astimezone(UTC)
            source_row = {name.title(): values[name] for name in required}
            checksum = hashlib.sha256(
                json.dumps(source_row, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            records.append(
                HistoricalBarRecord(
                    symbol=canonical_symbol,
                    interval="1d",
                    event_time=event_time,
                    publication_time=retrieved,
                    effective_time=event_time,
                    retrieval_time=retrieved,
                    open=prices["open"],
                    high=prices["high"],
                    low=prices["low"],
                    close=prices["close"],
                    adjusted_close=prices["close"],
                    volume=int(volume_decimal),
                    adjustment_status="provider_unspecified",
                    checksum=checksum,
                    provider_symbol=provider_symbol,
                    raw_metadata={
                        "source_row": source_row,
                        "provider_symbol": provider_symbol,
                        "content_type": payload.content_type or "unspecified",
                    },
                )
            )
        if not records:
            raise ProviderNoDataError("Stooq returned no data for the requested symbol and dates")
        return sorted(records, key=lambda record: record.event_time)

    def fetch_historical_bars(
        self, symbol: str, start: datetime, end: datetime, interval: str = "1d"
    ) -> list[HistoricalBarRecord]:
        params = self.request_parameters(symbol, start, end, interval)
        provider_symbol = params["s"]
        payload = self._get(params)
        return self._parse_csv(payload, symbol, provider_symbol, start, end)

    def fetch_asset_metadata(self, symbol: str) -> AssetMetadataRecord:
        now = datetime.now(UTC)
        canonical = symbol.strip().upper()
        provider_symbol = self.normalize_symbol(canonical)
        return AssetMetadataRecord(
            symbol=canonical,
            name=canonical,
            asset_type="Stock",
            exchange="XNYS",
            currency="USD",
            sector=None,
            industry=None,
            effective_time=now,
            retrieval_time=now,
            metadata={"provider_symbol": provider_symbol, "metadata_status": "symbol_only"},
        )

    def fetch_corporate_actions(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[CorporateActionRecord]:
        del symbol, start, end
        return []

    def fetch_exchange_calendar(
        self, exchange: str, start: datetime, end: datetime
    ) -> list[CalendarSessionRecord]:
        del exchange, start, end
        return []


class TwelveDataAdapter:
    """Documented Twelve Data daily OHLCV adapter with fail-closed validation."""

    code = "twelve_data"
    name = "Twelve Data Historical Daily Data"
    capabilities: tuple[str, ...] = ("historical_ohlcv", "asset_metadata")
    base_url = "https://api.twelvedata.com/time_series"
    allowed_host = "api.twelvedata.com"
    max_response_bytes = 2_000_000
    max_range_days = 3_650

    def __init__(
        self,
        api_key: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 10,
    ) -> None:
        self._api_key = api_key or os.getenv("MIL_TWELVE_DATA_API_KEY")
        self.transport = transport
        if timeout_seconds < 1 or timeout_seconds > 60:
            raise ValueError("Twelve Data timeout must be between 1 and 60 seconds")
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        normalized = symbol.strip().upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,15}", normalized):
            raise ProviderUnsupportedSymbolError("Unsupported Twelve Data symbol format")
        return normalized

    def health(self) -> dict[str, object]:
        return {
            "status": "unknown" if self._api_key else "unconfigured",
            "configured": bool(self._api_key),
            "connectivity": "not_tested",
            "provider": self.code,
            "authentication_required": True,
            "live_verified": False,
        }

    def _request(self, params: dict[str, str]) -> bytes:
        if not self._api_key:
            raise ProviderDisabledError("Twelve Data is not configured")
        try:
            with httpx.Client(
                timeout=httpx.Timeout(self.timeout_seconds),
                transport=self.transport,
                follow_redirects=False,
                headers={
                    "Authorization": f"apikey {self._api_key}",
                    "User-Agent": "Market-Intelligence-Lab/0.10.0",
                    "Accept": "application/json",
                },
            ) as client:
                response = client.get(self.base_url, params=params)
        except httpx.RequestError as exc:
            raise ProviderNetworkError("Twelve Data request timed out or was unavailable") from exc
        if response.url.scheme != "https" or response.url.host != self.allowed_host:
            raise ProviderAccessDeniedError("Twelve Data returned an unexpected response location")
        if len(response.content) > self.max_response_bytes:
            raise ProviderResponseTooLargeError("Twelve Data response exceeded the size limit")
        if response.status_code == 429:
            raise ProviderRateLimitError("Twelve Data rate limit reached; retry later")
        if response.status_code in {401, 403}:
            raise ProviderAccessDeniedError("Twelve Data rejected the configured credential")
        if response.status_code >= 500:
            raise ProviderTemporaryError("Twelve Data is temporarily unavailable")
        if response.status_code != 200:
            raise ProviderRejectedRequestError("Twelve Data rejected the bounded request")
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type not in {"application/json", "text/json", ""}:
            raise ProviderContentTypeError("Twelve Data returned a non-JSON response")
        return response.content

    def fetch_historical_bars(
        self, symbol: str, start: datetime, end: datetime, interval: str = "1d"
    ) -> list[HistoricalBarRecord]:
        if interval != "1d":
            raise ProviderInvalidDateRangeError("Twelve Data adapter supports daily bars only")
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ProviderInvalidDateRangeError("Date range must be timezone-aware and ordered")
        if (end - start).days > self.max_range_days:
            raise ProviderInvalidDateRangeError(
                f"Twelve Data date range cannot exceed {self.max_range_days} days"
            )
        canonical = self.normalize_symbol(symbol)
        body = self._request(
            {
                "symbol": canonical,
                "interval": "1day",
                "start_date": start.date().isoformat(),
                "end_date": end.date().isoformat(),
                "order": "ASC",
                "timezone": "America/New_York",
                "adjust": "all",
            }
        )
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderSchemaError("Twelve Data returned malformed JSON") from exc
        if not isinstance(payload, dict):
            raise ProviderSchemaError("Twelve Data response root was not an object")
        if payload.get("status") == "error" or "code" in payload and "values" not in payload:
            code = int(payload.get("code", 0) or 0)
            if code == 429:
                raise ProviderRateLimitError("Twelve Data rate limit reached; retry later")
            if code in {401, 403}:
                raise ProviderAccessDeniedError("Twelve Data rejected the configured credential")
            raise ProviderRejectedRequestError("Twelve Data returned a provider error")
        values = payload.get("values")
        if values in (None, []):
            raise ProviderNoDataError("Twelve Data returned no bars for the bounded request")
        if not isinstance(values, list) or len(values) > 10_000:
            raise ProviderSchemaError("Twelve Data returned an invalid values collection")
        retrieved = datetime.now(UTC)
        timezone = ZoneInfo("America/New_York")
        records: list[HistoricalBarRecord] = []
        seen: set[str] = set()
        for row in values:
            if not isinstance(row, dict):
                raise ProviderSchemaError("Twelve Data returned a malformed bar")
            required = {"datetime", "open", "high", "low", "close", "volume"}
            if not required.issubset(row):
                raise ProviderSchemaError("Twelve Data bar omitted required OHLCV fields")
            date_text = str(row["datetime"])
            try:
                session_date = datetime.strptime(date_text, "%Y-%m-%d").date()
                prices = {
                    name: Decimal(str(row[name])) for name in ("open", "high", "low", "close")
                }
                volume_decimal = Decimal(str(row["volume"]))
            except (ValueError, InvalidOperation) as exc:
                raise ProviderDataError("Twelve Data bar contained an invalid value") from exc
            if date_text in seen or session_date < start.date() or session_date > end.date():
                raise ProviderDataError("Twelve Data returned duplicate or out-of-range sessions")
            seen.add(date_text)
            if any(not value.is_finite() or value <= 0 for value in prices.values()):
                raise ProviderDataError("Twelve Data bar contained a non-positive price")
            if prices["high"] < max(prices["open"], prices["close"]) or prices["low"] > min(
                prices["open"], prices["close"]
            ):
                raise ProviderDataError("Twelve Data bar contained inconsistent OHLC values")
            if volume_decimal < 0 or volume_decimal != volume_decimal.to_integral_value():
                raise ProviderDataError("Twelve Data bar contained invalid volume")
            event_time = (
                datetime.combine(session_date, datetime.min.time(), tzinfo=timezone)
                + timedelta(hours=16)
            ).astimezone(UTC)
            normalized_row = {key: str(row[key]) for key in sorted(required)}
            checksum = hashlib.sha256(
                json.dumps(normalized_row, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            records.append(
                HistoricalBarRecord(
                    symbol=canonical,
                    interval="1d",
                    event_time=event_time,
                    publication_time=retrieved,
                    effective_time=event_time,
                    retrieval_time=retrieved,
                    open=prices["open"],
                    high=prices["high"],
                    low=prices["low"],
                    close=prices["close"],
                    adjusted_close=prices["close"],
                    volume=int(volume_decimal),
                    adjustment_status="provider_adjusted",
                    checksum=checksum,
                    provider_symbol=canonical,
                    raw_metadata={
                        "provider_timezone": "America/New_York",
                        "publication_time": "not_provided; retrieval time retained",
                    },
                )
            )
        return records

    def fetch_corporate_actions(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[CorporateActionRecord]:
        del symbol, start, end
        return []

    def fetch_asset_metadata(self, symbol: str) -> AssetMetadataRecord:
        raise ProviderDisabledError("Twelve Data metadata retrieval is not enabled in this sprint")

    def fetch_exchange_calendar(
        self, exchange: str, start: datetime, end: datetime
    ) -> list[CalendarSessionRecord]:
        del exchange, start, end
        return []


class SyntheticHistoricalAdapter:
    """Deterministic offline adapter used for tests and local demonstrations only."""

    code = "synthetic"
    name = "Deterministic Synthetic Demonstration Provider"
    capabilities = CAPABILITIES

    def health(self) -> dict[str, object]:
        return {
            "status": "healthy",
            "provider": self.code,
            "network_called": False,
            "message": "Deterministic offline demonstration adapter is available.",
        }

    def fetch_historical_bars(
        self, symbol: str, start: datetime, end: datetime, interval: str = "1d"
    ) -> list[HistoricalBarRecord]:
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("provider date ranges must be timezone-aware")
        normalized = symbol.strip().upper()
        seed = int(hashlib.sha256(normalized.encode()).hexdigest()[:8], 16)
        base = Decimal(str(50 + seed % 350))
        current = start.astimezone(UTC).replace(hour=21, minute=0, second=0, microsecond=0)
        finish = end.astimezone(UTC)
        records: list[HistoricalBarRecord] = []
        index = 0
        while current <= finish:
            if current.weekday() < 5:
                move = Decimal((seed + index * 17) % 13 - 6) / Decimal("1000")
                open_price = base * (Decimal("1") + move / Decimal("2"))
                close = base * (Decimal("1") + move)
                high = max(open_price, close) * Decimal("1.005")
                low = min(open_price, close) * Decimal("0.995")
                publication = current + timedelta(minutes=10)
                retrieval = current + timedelta(hours=5)
                canonical = (
                    f"{normalized}|{interval}|{current.isoformat()}|{open_price}|{high}|"
                    f"{low}|{close}|{1_000_000 + index}"
                )
                records.append(
                    HistoricalBarRecord(
                        symbol=normalized,
                        interval=interval,
                        event_time=current,
                        publication_time=publication,
                        effective_time=current,
                        retrieval_time=retrieval,
                        open=open_price,
                        high=high,
                        low=low,
                        close=close,
                        adjusted_close=close,
                        volume=1_000_000 + index,
                        adjustment_status="unadjusted",
                        checksum=hashlib.sha256(canonical.encode()).hexdigest(),
                    )
                )
                base = close
                index += 1
            current += timedelta(days=1)
        return records

    def fetch_corporate_actions(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[CorporateActionRecord]:
        return []

    def fetch_asset_metadata(self, symbol: str) -> AssetMetadataRecord:
        now = datetime.now(UTC)
        normalized = symbol.strip().upper()
        checksum = hashlib.sha256(f"synthetic|metadata|{normalized}".encode()).hexdigest()
        return AssetMetadataRecord(
            symbol=normalized,
            name=f"{normalized} Demonstration Asset",
            asset_type="Stock",
            exchange="XNYS",
            currency="USD",
            sector=None,
            industry=None,
            effective_time=now,
            retrieval_time=now,
            metadata={"demonstration": True},
            checksum=checksum,
        )

    def fetch_exchange_calendar(
        self, exchange: str, start: datetime, end: datetime
    ) -> list[CalendarSessionRecord]:
        current = start.astimezone(UTC).date()
        finish = end.astimezone(UTC).date()
        sessions: list[CalendarSessionRecord] = []
        while current <= finish:
            if current.weekday() < 5:
                sessions.append(
                    CalendarSessionRecord(
                        calendar_code=exchange.upper(),
                        session_date=current.isoformat(),
                        open_time=datetime.combine(current, datetime.min.time(), tzinfo=UTC)
                        + timedelta(hours=14, minutes=30),
                        close_time=datetime.combine(current, datetime.min.time(), tzinfo=UTC)
                        + timedelta(hours=21),
                    )
                )
            current += timedelta(days=1)
        return sessions
