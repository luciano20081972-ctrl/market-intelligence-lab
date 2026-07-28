from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from packages.strategies.builtins import (
    BuyAndHoldParameters,
    EqualWeightParameters,
    MeanReversionParameters,
    MomentumParameters,
    MovingAverageParameters,
    RSIParameters,
    VolatilityBreakoutParameters,
    buy_and_hold,
    equal_weight_rebalance,
    mean_reversion,
    momentum,
    moving_average_crossover,
    rsi_threshold,
    volatility_breakout,
)
from packages.strategies.types import StrategyDefinition

STRATEGY_DEFINITIONS: dict[str, StrategyDefinition] = {
    definition.key: definition
    for definition in (
        StrategyDefinition(
            "buy_and_hold",
            "Buy and Hold",
            "Buy each selected asset once and retain it.",
            "A target weight is emitted from the first bar and becomes eligible only "
            "on a later bar.",
            BuyAndHoldParameters,
            buy_and_hold,
        ),
        StrategyDefinition(
            "moving_average_crossover",
            "Moving-Average Crossover",
            "Follow the direction of short and long simple moving averages.",
            "Long while the short SMA is strictly above the long SMA; otherwise flat.",
            MovingAverageParameters,
            moving_average_crossover,
        ),
        StrategyDefinition(
            "momentum",
            "Momentum",
            "Hold assets with positive configured trailing return.",
            "Trailing return uses only closes at or before signal time.",
            MomentumParameters,
            momentum,
        ),
        StrategyDefinition(
            "mean_reversion",
            "Mean Reversion",
            "Buy statistically depressed prices and exit after reversion.",
            "A rolling z-score compares the current close with its trailing sample "
            "mean and deviation.",
            MeanReversionParameters,
            mean_reversion,
        ),
        StrategyDefinition(
            "rsi_threshold",
            "RSI Threshold",
            "Trade deterministic Wilder RSI thresholds.",
            "Buy at or below oversold and exit at or above overbought; values between "
            "thresholds preserve the prior target.",
            RSIParameters,
            rsi_threshold,
        ),
        StrategyDefinition(
            "volatility_breakout",
            "Volatility Breakout",
            "Hold assets closing above a prior rolling high.",
            "The current close is compared only with earlier closes in the lookback window.",
            VolatilityBreakoutParameters,
            volatility_breakout,
        ),
        StrategyDefinition(
            "equal_weight_rebalance",
            "Equal-Weight Periodic Rebalance",
            "Rebalance selected assets to equal long-only weights.",
            "Target weights are emitted every configured number of observations and "
            "normalized across selected assets.",
            EqualWeightParameters,
            equal_weight_rebalance,
        ),
    )
}


def get_strategy_definition(strategy_type: str) -> StrategyDefinition:
    try:
        return STRATEGY_DEFINITIONS[strategy_type]
    except KeyError as exc:
        supported = ", ".join(sorted(STRATEGY_DEFINITIONS))
        raise ValueError(
            f"Unknown strategy type '{strategy_type}'. Supported: {supported}"
        ) from exc


def validate_strategy_parameters(strategy_type: str, parameters: dict[str, Any]) -> dict[str, Any]:
    definition = get_strategy_definition(strategy_type)
    try:
        return definition.parameters_model.model_validate(parameters).model_dump(mode="json")
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def default_strategy_parameters(strategy_type: str) -> dict[str, Any]:
    definition = get_strategy_definition(strategy_type)
    return definition.parameters_model().model_dump(mode="json")
