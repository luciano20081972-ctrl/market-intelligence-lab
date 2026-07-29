from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from packages.market_data.types import (
    CAPABILITIES,
    AssetMetadataRecord,
    CalendarSessionRecord,
    CorporateActionRecord,
    HistoricalBarRecord,
    ProviderDisabledError,
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
