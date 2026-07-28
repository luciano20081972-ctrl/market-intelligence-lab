"""Backtest result types that keep simulated performance separate from live claims."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestSummary:
    strategy_name: str
    observations: int
    simulated_return: float
    max_drawdown: float
