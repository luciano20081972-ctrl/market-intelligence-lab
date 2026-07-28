from __future__ import annotations

import statistics
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.strategies.indicators import relative_strength_index, simple_moving_average
from packages.strategies.types import SignalDecision


class StrictParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BuyAndHoldParameters(StrictParameters):
    pass


class MovingAverageParameters(StrictParameters):
    short_window: int = Field(default=20, ge=2, le=100)
    long_window: int = Field(default=50, ge=3, le=250)

    @model_validator(mode="after")
    def windows_in_order(self) -> MovingAverageParameters:
        if self.short_window >= self.long_window:
            raise ValueError("short_window must be less than long_window")
        return self


class MomentumParameters(StrictParameters):
    lookback: int = Field(default=20, ge=2, le=250)
    minimum_return: float = Field(default=0.0, ge=-1, le=5)


class MeanReversionParameters(StrictParameters):
    lookback: int = Field(default=20, ge=3, le=250)
    entry_z_score: float = Field(default=1.0, gt=0, le=5)
    exit_z_score: float = Field(default=0.2, ge=0, le=2)

    @model_validator(mode="after")
    def exit_inside_entry(self) -> MeanReversionParameters:
        if self.exit_z_score >= self.entry_z_score:
            raise ValueError("exit_z_score must be less than entry_z_score")
        return self


class RSIParameters(StrictParameters):
    period: int = Field(default=14, ge=2, le=100)
    oversold: float = Field(default=30, ge=1, le=49)
    overbought: float = Field(default=70, ge=51, le=99)


class VolatilityBreakoutParameters(StrictParameters):
    lookback: int = Field(default=20, ge=2, le=250)
    breakout_buffer: float = Field(default=0.0, ge=0, le=0.25)


class EqualWeightParameters(StrictParameters):
    rebalance_days: int = Field(default=21, ge=1, le=252)


def buy_and_hold(closes: Sequence[float], index: int, params: BaseModel) -> SignalDecision:
    del closes, params
    target = 1.0 if index == 0 else None
    return SignalDecision(
        target,
        "long" if target else "hold",
        1.0 if target else 0.0,
        "Buy once after the first observed bar and hold.",
        {"observation_index": float(index)},
    )


def moving_average_crossover(
    closes: Sequence[float], index: int, params: BaseModel
) -> SignalDecision:
    values = MovingAverageParameters.model_validate(params)
    short = simple_moving_average(closes[: index + 1], values.short_window)[-1]
    long = simple_moving_average(closes[: index + 1], values.long_window)[-1]
    if short is None or long is None:
        return SignalDecision(None, "hold", 0.0, "Waiting for moving-average warm-up.", {})
    long_signal = short > long
    return SignalDecision(
        float(long_signal),
        "long" if long_signal else "flat",
        abs(short / long - 1),
        "Long when the short SMA is above the long SMA.",
        {"short_sma": short, "long_sma": long},
    )


def momentum(closes: Sequence[float], index: int, params: BaseModel) -> SignalDecision:
    values = MomentumParameters.model_validate(params)
    if index < values.lookback:
        return SignalDecision(None, "hold", 0.0, "Waiting for momentum lookback.", {})
    momentum_return = closes[index] / closes[index - values.lookback] - 1
    long_signal = momentum_return > values.minimum_return
    return SignalDecision(
        float(long_signal),
        "long" if long_signal else "flat",
        abs(momentum_return),
        "Long when trailing return exceeds the configured threshold.",
        {"momentum_return": momentum_return},
    )


def mean_reversion(closes: Sequence[float], index: int, params: BaseModel) -> SignalDecision:
    values = MeanReversionParameters.model_validate(params)
    if index + 1 < values.lookback:
        return SignalDecision(None, "hold", 0.0, "Waiting for mean-reversion lookback.", {})
    window = closes[index - values.lookback + 1 : index + 1]
    mean = statistics.fmean(window)
    deviation = statistics.stdev(window)
    z_score = (closes[index] - mean) / deviation if deviation else 0.0
    if z_score <= -values.entry_z_score:
        target, direction = 1.0, "long"
    elif z_score >= -values.exit_z_score:
        target, direction = 0.0, "flat"
    else:
        target, direction = None, "hold"
    return SignalDecision(
        target,
        direction,
        abs(z_score),
        "Buy statistically depressed closes and exit after reversion.",
        {"z_score": z_score, "rolling_mean": mean},
    )


def rsi_threshold(closes: Sequence[float], index: int, params: BaseModel) -> SignalDecision:
    values = RSIParameters.model_validate(params)
    rsi_value = relative_strength_index(closes[: index + 1], values.period)[-1]
    if rsi_value is None:
        return SignalDecision(None, "hold", 0.0, "Waiting for RSI warm-up.", {})
    if rsi_value <= values.oversold:
        target, direction = 1.0, "long"
    elif rsi_value >= values.overbought:
        target, direction = 0.0, "flat"
    else:
        target, direction = None, "hold"
    return SignalDecision(
        target,
        direction,
        abs(50 - rsi_value) / 50,
        "Buy below the oversold RSI threshold and exit above the overbought threshold.",
        {"rsi": rsi_value},
    )


def volatility_breakout(closes: Sequence[float], index: int, params: BaseModel) -> SignalDecision:
    values = VolatilityBreakoutParameters.model_validate(params)
    if index < values.lookback:
        return SignalDecision(None, "hold", 0.0, "Waiting for breakout lookback.", {})
    prior_high = max(closes[index - values.lookback : index])
    threshold = prior_high * (1 + values.breakout_buffer)
    long_signal = closes[index] > threshold
    return SignalDecision(
        float(long_signal),
        "long" if long_signal else "flat",
        max(closes[index] / threshold - 1, 0.0),
        "Long when the close exceeds the prior rolling high plus buffer.",
        {"breakout_threshold": threshold},
    )


def equal_weight_rebalance(
    closes: Sequence[float], index: int, params: BaseModel
) -> SignalDecision:
    del closes
    values = EqualWeightParameters.model_validate(params)
    rebalance = index % values.rebalance_days == 0
    return SignalDecision(
        1.0 if rebalance else None,
        "long" if rebalance else "hold",
        1.0 if rebalance else 0.0,
        "Rebalance all selected assets to equal weights on the configured schedule.",
        {"rebalance_day": float(index)},
    )
