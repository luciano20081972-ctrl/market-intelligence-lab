from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class ProviderPriceBar:
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
    is_demonstration_data: bool


class MarketDataProvider(Protocol):
    """Stable boundary for future live providers."""

    name: str
    provider_type: str

    def health(self) -> str: ...

    def fetch_daily_bars(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[ProviderPriceBar]: ...
