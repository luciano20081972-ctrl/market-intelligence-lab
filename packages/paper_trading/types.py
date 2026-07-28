from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_order_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._:-]+$")
    symbol: str = Field(min_length=1, max_length=16, pattern=r"^[A-Za-z][A-Za-z0-9.\-]*$")
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit", "stop", "stop_limit"]
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    limit_price: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=8)
    stop_price: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=8)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_order_prices(self) -> OrderRequest:
        if self.order_type in {"limit", "stop_limit"} and self.limit_price is None:
            raise ValueError("limit_price is required for limit and stop-limit orders")
        if self.order_type in {"stop", "stop_limit"} and self.stop_price is None:
            raise ValueError("stop_price is required for stop and stop-limit orders")
        if self.order_type == "market" and (
            self.limit_price is not None or self.stop_price is not None
        ):
            raise ValueError("market orders cannot specify limit_price or stop_price")
        return self


@dataclass(frozen=True)
class ExecutionAssumptions:
    commission: Decimal = Decimal("1.00")
    spread_bps: Decimal = Decimal("2")
    slippage_bps: Decimal = Decimal("1")


@dataclass(frozen=True)
class OrderPreview:
    outcome: str
    estimated_price: Decimal | None
    estimated_value: Decimal | None
    estimated_fees: Decimal
    rejection_reasons: list[str]
    source_price_bar_id: UUID
    assumptions: dict[str, str]
    is_triggered: bool = False


@dataclass(frozen=True)
class OrderResult:
    order_id: UUID
    status: str
    rejection_reason: str | None
    idempotent_replay: bool
