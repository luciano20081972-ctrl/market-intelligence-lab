from __future__ import annotations

import math
from collections.abc import Sequence
from decimal import Decimal

Number = float | int | Decimal


def _float_values(values: Sequence[Number]) -> list[float]:
    return [float(value) for value in values]


def simple_moving_average(values: Sequence[Number], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    numeric = _float_values(values)
    result: list[float | None] = [None] * len(numeric)
    rolling = 0.0
    for index, value in enumerate(numeric):
        rolling += value
        if index >= period:
            rolling -= numeric[index - period]
        if index >= period - 1:
            result[index] = rolling / period
    return result


def exponential_moving_average(values: Sequence[Number], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    numeric = _float_values(values)
    result: list[float | None] = [None] * len(numeric)
    if len(numeric) < period:
        return result
    current = sum(numeric[:period]) / period
    result[period - 1] = current
    multiplier = 2 / (period + 1)
    for index in range(period, len(numeric)):
        current = (numeric[index] - current) * multiplier + current
        result[index] = current
    return result


def relative_strength_index(values: Sequence[Number], period: int = 14) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    numeric = _float_values(values)
    result: list[float | None] = [None] * len(numeric)
    if len(numeric) <= period:
        return result
    changes = [numeric[index] - numeric[index - 1] for index in range(1, len(numeric))]
    average_gain = sum(max(change, 0) for change in changes[:period]) / period
    average_loss = sum(max(-change, 0) for change in changes[:period]) / period

    def rsi(gain: float, loss: float) -> float:
        if loss == 0:
            return 100.0 if gain > 0 else 50.0
        return 100 - (100 / (1 + gain / loss))

    result[period] = rsi(average_gain, average_loss)
    for index in range(period + 1, len(numeric)):
        change = changes[index - 1]
        average_gain = ((average_gain * (period - 1)) + max(change, 0)) / period
        average_loss = ((average_loss * (period - 1)) + max(-change, 0)) / period
        result[index] = rsi(average_gain, average_loss)
    return result


def moving_average_convergence_divergence(
    values: Sequence[Number], fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    if fast >= slow:
        raise ValueError("fast period must be less than slow period")
    fast_values = exponential_moving_average(values, fast)
    slow_values = exponential_moving_average(values, slow)
    macd: list[float | None] = [
        (fast_value - slow_value) if fast_value is not None and slow_value is not None else None
        for fast_value, slow_value in zip(fast_values, slow_values, strict=True)
    ]
    valid = [value for value in macd if value is not None]
    signal_valid = exponential_moving_average(valid, signal)
    signal_line: list[float | None] = [None] * len(macd)
    valid_index = 0
    for index, value in enumerate(macd):
        if value is not None:
            signal_line[index] = signal_valid[valid_index]
            valid_index += 1
    histogram = [
        (value - signal_value) if value is not None and signal_value is not None else None
        for value, signal_value in zip(macd, signal_line, strict=True)
    ]
    return macd, signal_line, histogram


def average_true_range(
    highs: Sequence[Number], lows: Sequence[Number], closes: Sequence[Number], period: int = 14
) -> list[float | None]:
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("high, low, and close series must be the same length")
    if period <= 0:
        raise ValueError("period must be positive")
    high_values, low_values, close_values = map(_float_values, (highs, lows, closes))
    true_ranges: list[float] = []
    for index, (high, low) in enumerate(zip(high_values, low_values, strict=True)):
        if index == 0:
            true_ranges.append(high - low)
        else:
            previous_close = close_values[index - 1]
            true_ranges.append(
                max(high - low, abs(high - previous_close), abs(low - previous_close))
            )
    result: list[float | None] = [None] * len(true_ranges)
    if len(true_ranges) < period:
        return result
    current = sum(true_ranges[:period]) / period
    result[period - 1] = current
    for index in range(period, len(true_ranges)):
        current = ((current * (period - 1)) + true_ranges[index]) / period
        result[index] = current
    return result


def daily_return(values: Sequence[Number]) -> list[float | None]:
    numeric = _float_values(values)
    result: list[float | None] = [None] * len(numeric)
    for index in range(1, len(numeric)):
        previous = numeric[index - 1]
        result[index] = numeric[index] / previous - 1 if previous else None
    return result


def cumulative_return(values: Sequence[Number]) -> list[float | None]:
    numeric = _float_values(values)
    if not numeric:
        return []
    base = numeric[0]
    return [(value / base - 1) if base else None for value in numeric]


def rolling_volatility(
    values: Sequence[Number], period: int = 20, annualization: int = 252
) -> list[float | None]:
    returns = daily_return(values)
    result: list[float | None] = [None] * len(returns)
    for index in range(period, len(returns)):
        window = [value for value in returns[index - period + 1 : index + 1] if value is not None]
        if len(window) == period:
            mean = sum(window) / period
            variance = sum((value - mean) ** 2 for value in window) / max(period - 1, 1)
            result[index] = math.sqrt(variance) * math.sqrt(annualization)
    return result


def volume_moving_average(volumes: Sequence[Number], period: int = 20) -> list[float | None]:
    return simple_moving_average(volumes, period)


def relative_strength(
    values: Sequence[Number], benchmark_values: Sequence[Number]
) -> list[float | None]:
    if len(values) != len(benchmark_values):
        raise ValueError("asset and benchmark series must be the same length")
    asset = _float_values(values)
    benchmark = _float_values(benchmark_values)
    if not asset:
        return []
    base_ratio = asset[0] / benchmark[0]
    return [
        ((a / b) / base_ratio - 1) if b and base_ratio else None
        for a, b in zip(asset, benchmark, strict=True)
    ]


def rolling_drawdown(values: Sequence[Number], period: int | None = None) -> list[float | None]:
    numeric = _float_values(values)
    result: list[float | None] = []
    for index, value in enumerate(numeric):
        start = 0 if period is None else max(0, index - period + 1)
        peak = max(numeric[start : index + 1])
        result.append(value / peak - 1 if peak else None)
    return result
