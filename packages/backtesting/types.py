from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BacktestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbols: list[str] = Field(min_length=1, max_length=25)
    benchmark_symbol: str = "SPY"
    initial_cash: Decimal = Field(default=Decimal("100000"), gt=0, max_digits=20, decimal_places=2)
    commission: Decimal = Field(default=Decimal("1.00"), ge=0, le=Decimal("1000"))
    spread_bps: Decimal = Field(default=Decimal("2"), ge=0, le=Decimal("500"))
    slippage_bps: Decimal = Field(default=Decimal("1"), ge=0, le=Decimal("500"))
    execution_delay: int = Field(default=1, ge=1, le=20)
    max_position_pct: Decimal = Field(default=Decimal("0.40"), gt=0, le=1)
    max_total_exposure: Decimal = Field(default=Decimal("1.00"), gt=0, le=1)

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, symbols: list[str]) -> list[str]:
        normalized = [symbol.strip().upper() for symbol in symbols]
        if any(not symbol for symbol in normalized):
            raise ValueError("symbols cannot contain blanks")
        if len(set(normalized)) != len(normalized):
            raise ValueError("symbols must be unique")
        return normalized

    @field_validator("benchmark_symbol")
    @classmethod
    def normalize_benchmark(cls, symbol: str) -> str:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("benchmark_symbol cannot be blank")
        return normalized


@dataclass(frozen=True)
class HistoricalBar:
    id: uuid.UUID
    asset_id: uuid.UUID
    data_source_id: uuid.UUID
    symbol: str
    event_time: datetime
    publication_time: datetime
    effective_time: datetime
    retrieval_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass(frozen=True)
class SimulatedTrade:
    asset_id: uuid.UUID
    source_price_bar_id: uuid.UUID
    symbol: str
    side: str
    signal_time: datetime
    execution_time: datetime
    quantity: Decimal
    price: Decimal
    gross_value: Decimal
    fees: Decimal
    cash_after: Decimal
    reason: str
    realized_pnl: Decimal
    holding_days: int


@dataclass(frozen=True)
class DailySnapshot:
    event_time: datetime
    equity: Decimal
    cash: Decimal
    positions: dict[str, dict[str, str]]
    cumulative_fees: Decimal
    exposure: Decimal
    drawdown: Decimal
    benchmark_value: Decimal


@dataclass(frozen=True)
class GeneratedSignal:
    asset_id: uuid.UUID
    source_price_bar_id: uuid.UUID
    symbol: str
    generated_at: datetime
    eligible_after: datetime
    direction: str
    strength: Decimal
    explanation: str
    factors: dict[str, Decimal]


@dataclass
class BacktestResult:
    trades: list[SimulatedTrade] = field(default_factory=list)
    snapshots: list[DailySnapshot] = field(default_factory=list)
    signals: list[GeneratedSignal] = field(default_factory=list)
    rejections: list[str] = field(default_factory=list)
    metrics: dict[str, float | int | str] = field(default_factory=dict)
    source_data_identifiers: list[str] = field(default_factory=list)
    data_source_identifiers: list[str] = field(default_factory=list)
    assumptions: dict[str, Any] = field(default_factory=dict)
