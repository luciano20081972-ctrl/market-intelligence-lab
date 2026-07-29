from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx

from packages.market_data.types import (
    CAPABILITIES,
    AssetMetadataRecord,
    CalendarSessionRecord,
    CorporateActionRecord,
    HistoricalBarRecord,
    ProviderDisabledError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTemporaryError,
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
        if not canonical or len(canonical) > 16:
            raise ValueError("symbol must contain between 1 and 16 characters")
        if canonical.startswith("^") or "." in canonical:
            return canonical.lower()
        return f"{canonical.lower()}.us"

    def health(self) -> dict[str, object]:
        return {
            "status": "healthy",
            "configured": True,
            "connectivity": "not_tested",
            "provider": self.code,
            "authentication_required": False,
            "base_url": self.base_url,
        }

    def test_connectivity(self) -> dict[str, object]:
        body = self._get({"s": "aapl.us", "d1": "20260102", "d2": "20260109", "i": "d"})
        header = body.decode("utf-8-sig", errors="replace").splitlines()[0]
        if header.strip() != "Date,Open,High,Low,Close,Volume":
            raise ProviderResponseError("Stooq connectivity response was malformed")
        return {**self.health(), "connectivity": "connected"}

    def _get(self, params: dict[str, str]) -> bytes:
        try:
            with httpx.Client(
                timeout=httpx.Timeout(self.timeout_seconds),
                transport=self.transport,
                follow_redirects=False,
                headers={"User-Agent": "Market-Intelligence-Lab/0.4"},
            ) as client:
                response = client.get(self.base_url, params=params)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderTemporaryError("Stooq request timed out or was unavailable") from exc
        if response.status_code == 429:
            raise ProviderRateLimitError("Stooq rate limit reached; retry later")
        if response.status_code >= 500:
            raise ProviderTemporaryError(f"Stooq temporarily returned HTTP {response.status_code}")
        if response.status_code != 200:
            raise ProviderError(f"Stooq rejected the request with HTTP {response.status_code}")
        body = response.content
        if len(body) > self.max_response_bytes:
            raise ProviderResponseError("Stooq response exceeded the configured size limit")
        if not body.strip():
            raise ProviderResponseError("Stooq returned an empty response")
        return body

    def fetch_historical_bars(
        self, symbol: str, start: datetime, end: datetime, interval: str = "1d"
    ) -> list[HistoricalBarRecord]:
        if interval != "1d":
            raise ValueError("Stooq adapter supports daily bars only")
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ValueError("start/end must be timezone-aware and ordered")
        if (end - start).days > self.max_range_days:
            raise ValueError(f"Stooq date range cannot exceed {self.max_range_days} days")
        provider_symbol = self.normalize_symbol(symbol)
        body = self._get(
            {
                "s": provider_symbol,
                "d1": start.strftime("%Y%m%d"),
                "d2": end.strftime("%Y%m%d"),
                "i": "d",
            }
        )
        try:
            text = body.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ProviderResponseError("Stooq response was not valid UTF-8 CSV") from exc
        reader = csv.DictReader(io.StringIO(text))
        required = {"Date", "Open", "High", "Low", "Close", "Volume"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ProviderResponseError("Stooq CSV columns were missing or malformed")
        retrieved = datetime.now(UTC)
        timezone = ZoneInfo("America/New_York")
        records: list[HistoricalBarRecord] = []
        try:
            for row in reader:
                if any(row.get(field, "").strip() in {"", "N/D"} for field in required):
                    raise ProviderResponseError("Stooq CSV contained a missing market value")
                session_date = datetime.strptime(row["Date"], "%Y-%m-%d").date()
                close_local = datetime.combine(
                    session_date, datetime.min.time(), tzinfo=timezone
                ) + timedelta(hours=16)
                event_time = close_local.astimezone(UTC)
                raw = {key: row[key] for key in sorted(required)}
                checksum = hashlib.sha256(
                    json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                records.append(
                    HistoricalBarRecord(
                        symbol=symbol.strip().upper(),
                        interval="1d",
                        event_time=event_time,
                        publication_time=retrieved,
                        effective_time=event_time,
                        retrieval_time=retrieved,
                        open=Decimal(row["Open"]),
                        high=Decimal(row["High"]),
                        low=Decimal(row["Low"]),
                        close=Decimal(row["Close"]),
                        adjusted_close=Decimal(row["Close"]),
                        volume=int(Decimal(row["Volume"])),
                        adjustment_status="provider_unspecified",
                        checksum=checksum,
                        provider_symbol=provider_symbol,
                        raw_metadata={"source_row": raw, "provider_symbol": provider_symbol},
                    )
                )
        except ProviderResponseError:
            raise
        except (KeyError, ValueError, ArithmeticError) as exc:
            raise ProviderResponseError("Stooq CSV contained an invalid market value") from exc
        if not records:
            raise ProviderResponseError("Stooq returned no data for the requested symbol and dates")
        return records

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
