from __future__ import annotations

import math
from statistics import fmean, stdev

from packages.backtesting.types import DailySnapshot, SimulatedTrade


def calculate_metrics(
    snapshots: list[DailySnapshot], trades: list[SimulatedTrade], initial_cash: float
) -> dict[str, float | int | str]:
    if not snapshots:
        raise ValueError("at least one daily snapshot is required")
    equities = [float(snapshot.equity) for snapshot in snapshots]
    daily_returns = [
        equities[index] / equities[index - 1] - 1
        for index in range(1, len(equities))
        if equities[index - 1]
    ]
    total_return = equities[-1] / initial_cash - 1
    years = max((snapshots[-1].event_time - snapshots[0].event_time).days / 365.25, 1 / 252)
    annualized_return = (
        (equities[-1] / initial_cash) ** (1 / years) - 1 if equities[-1] > 0 else -1.0
    )
    annualized_volatility = stdev(daily_returns) * math.sqrt(252) if len(daily_returns) > 1 else 0.0
    mean_return = fmean(daily_returns) if daily_returns else 0.0
    sharpe = (
        mean_return / stdev(daily_returns) * math.sqrt(252)
        if len(daily_returns) > 1 and stdev(daily_returns)
        else 0.0
    )
    downside = [min(value, 0.0) for value in daily_returns]
    downside_deviation = (
        math.sqrt(fmean([value * value for value in downside])) if downside else 0.0
    )
    sortino = mean_return / downside_deviation * math.sqrt(252) if downside_deviation else 0.0
    max_drawdown = min(float(snapshot.drawdown) for snapshot in snapshots)
    calmar = annualized_return / abs(max_drawdown) if max_drawdown else 0.0
    realized = [float(trade.realized_pnl) for trade in trades if trade.side == "sell"]
    gains = [value for value in realized if value > 0]
    losses = [value for value in realized if value < 0]
    gross_profit = sum(gains)
    gross_loss = abs(sum(losses))
    completed = len(realized)
    benchmark_return = float(snapshots[-1].benchmark_value) / initial_cash - 1
    average_equity = fmean(equities)
    turnover = (
        sum(float(trade.gross_value) for trade in trades) / average_equity
        if average_equity
        else 0.0
    )
    return {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "maximum_drawdown": max_drawdown,
        "calmar_ratio": calmar,
        "win_rate": len(gains) / completed if completed else 0.0,
        "profit_factor": gross_profit / gross_loss
        if gross_loss
        else (gross_profit if gross_profit else 0.0),
        "average_gain": fmean(gains) if gains else 0.0,
        "average_loss": fmean(losses) if losses else 0.0,
        "turnover": turnover,
        "number_of_trades": len(trades),
        "average_holding_period": fmean(
            [trade.holding_days for trade in trades if trade.side == "sell"]
        )
        if completed
        else 0.0,
        "benchmark_return": benchmark_return,
        "excess_return": total_return - benchmark_return,
        "final_equity": equities[-1],
        "cash_balance": float(snapshots[-1].cash),
        "exposure": float(snapshots[-1].exposure),
        "hypothetical": "true",
    }
