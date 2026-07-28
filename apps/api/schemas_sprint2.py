from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.paper_trading.types import OrderRequest


class StrategyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    strategy_type: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=2000)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value


class StrategyVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parameters: dict[str, Any]


class StrategyVersionResponse(BaseModel):
    id: UUID
    version: int
    parameters: dict[str, Any]
    parameter_schema: dict[str, Any]
    calculation_notes: str
    created_at: datetime


class StrategyResponse(BaseModel):
    id: UUID
    name: str
    strategy_type: str
    description: str
    is_builtin: bool
    latest_version: StrategyVersionResponse
    versions: list[StrategyVersionResponse] = Field(default_factory=list)


class StrategyPage(BaseModel):
    items: list[StrategyResponse]
    page: int
    page_size: int
    total: int


class BacktestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy_version_id: UUID
    parameters: dict[str, Any] | None = None
    symbols: list[str] = Field(min_length=1, max_length=25)
    benchmark_symbol: str = "SPY"
    start_time: datetime
    end_time: datetime
    initial_cash: Decimal = Field(default=Decimal("100000"), gt=0)
    commission: Decimal = Field(default=Decimal("1.00"), ge=0)
    spread_bps: Decimal = Field(default=Decimal("2"), ge=0, le=500)
    slippage_bps: Decimal = Field(default=Decimal("1"), ge=0, le=500)
    execution_delay: int = Field(default=1, ge=1, le=20)
    max_position_pct: Decimal = Field(default=Decimal("0.40"), gt=0, le=1)
    max_total_exposure: Decimal = Field(default=Decimal("1.00"), gt=0, le=1)

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, values: list[str]) -> list[str]:
        return [value.strip().upper() for value in values]

    @field_validator("benchmark_symbol")
    @classmethod
    def normalize_benchmark(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_range(self) -> BacktestCreate:
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("start_time and end_time must include a timezone")
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class BacktestSummaryResponse(BaseModel):
    id: UUID
    strategy_version_id: UUID
    strategy_name: str
    strategy_type: str
    status: str
    asset_symbols: list[str]
    benchmark_symbol: str
    start_time: datetime
    end_time: datetime
    initial_cash: Decimal
    final_equity: Decimal
    cash_balance: Decimal
    metrics: dict[str, Any]
    strategy_configuration: dict[str, Any]
    risk_configuration: dict[str, Any]
    execution_assumptions: dict[str, Any]
    data_source_identifiers: list[str]
    application_version: str
    is_hypothetical: bool
    created_at: datetime


class BacktestPage(BaseModel):
    items: list[BacktestSummaryResponse]
    page: int
    page_size: int
    total: int


class BacktestTradeResponse(BaseModel):
    id: UUID
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
    source_price_bar_id: UUID


class EquityPointResponse(BaseModel):
    event_time: datetime
    equity: Decimal
    benchmark_value: Decimal
    cash: Decimal
    exposure: Decimal
    drawdown: Decimal
    cumulative_fees: Decimal


class PaperPortfolioCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    starting_cash: Decimal = Field(gt=0, max_digits=20, decimal_places=2)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value


class PositionResponse(BaseModel):
    id: UUID
    symbol: str
    name: str
    sector: str | None
    quantity: Decimal
    average_cost: Decimal
    mark_price: Decimal | None
    market_value: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal


class PaperPortfolioResponse(BaseModel):
    id: UUID
    name: str
    currency: str
    starting_cash: Decimal
    cash_balance: Decimal
    portfolio_value: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    exposure: Decimal
    status: str
    positions: list[PositionResponse]
    open_order_count: int
    created_at: datetime
    updated_at: datetime
    warning: str = "Hypothetical simulated portfolio — no real orders."


class OrderPreviewResponse(BaseModel):
    outcome: str
    estimated_price: Decimal | None
    estimated_value: Decimal | None
    estimated_fees: Decimal
    rejection_reasons: list[str]
    source_price_bar_id: UUID
    assumptions: dict[str, str]
    is_triggered: bool


class OrderResponse(BaseModel):
    id: UUID
    client_order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: Decimal
    limit_price: Decimal | None
    stop_price: Decimal | None
    status: str
    is_triggered: bool
    rejection_reason: str | None
    estimated_value: Decimal | None
    estimated_fees: Decimal | None
    submitted_at: datetime
    cancelled_at: datetime | None
    idempotent_replay: bool = False


class FillResponse(BaseModel):
    id: UUID
    order_id: UUID
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    gross_value: Decimal
    fees: Decimal
    filled_at: datetime
    source_price_bar_id: UUID


class RiskRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit_value: Decimal = Field(ge=0)
    is_enabled: bool = True


class RiskRuleResponse(BaseModel):
    id: UUID
    rule_type: str
    limit_value: Decimal
    is_enabled: bool
    configuration: dict[str, Any]


class PerformanceResponse(BaseModel):
    portfolio_id: UUID
    starting_cash: Decimal
    current_value: Decimal
    total_return: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    points: list[dict[str, Any]]
    warning: str = "Hypothetical simulated results — not actual performance."


OrderPayload = OrderRequest
