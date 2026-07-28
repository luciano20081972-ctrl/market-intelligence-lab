import math

import pytest

from packages.strategies.indicators import (
    average_true_range,
    cumulative_return,
    daily_return,
    exponential_moving_average,
    moving_average_convergence_divergence,
    relative_strength,
    relative_strength_index,
    rolling_drawdown,
    rolling_volatility,
    simple_moving_average,
    volume_moving_average,
)


def test_simple_and_exponential_moving_averages() -> None:
    values = [1, 2, 3, 4, 5]
    assert simple_moving_average(values, 3) == [None, None, 2.0, 3.0, 4.0]
    assert exponential_moving_average(values, 3) == [None, None, 2.0, 3.0, 4.0]


def test_rsi_wilder_edge_cases() -> None:
    assert relative_strength_index(list(range(1, 17)), 14)[-1] == 100.0
    assert relative_strength_index([10] * 16, 14)[-1] == 50.0


def test_macd_alignment_and_histogram() -> None:
    macd, signal, histogram = moving_average_convergence_divergence(
        list(range(1, 50)), fast=3, slow=6, signal=3
    )
    assert len(macd) == len(signal) == len(histogram) == 49
    assert macd[-1] == pytest.approx(1.5)
    assert signal[-1] == pytest.approx(1.5)
    assert histogram[-1] == pytest.approx(0)


def test_average_true_range_uses_gaps() -> None:
    atr = average_true_range([10, 12, 13], [8, 9, 11], [9, 11, 12], period=2)
    assert atr == [None, 2.5, 2.25]


def test_return_and_drawdown_indicators() -> None:
    values = [100, 110, 99, 120]
    assert daily_return(values) == [
        None,
        pytest.approx(0.1),
        pytest.approx(-0.1),
        pytest.approx(120 / 99 - 1),
    ]
    assert cumulative_return(values) == [
        0.0,
        pytest.approx(0.1),
        pytest.approx(-0.01),
        pytest.approx(0.2),
    ]
    assert rolling_drawdown(values) == [0.0, 0.0, pytest.approx(-0.1), 0.0]


def test_volatility_volume_and_relative_strength() -> None:
    values = [100, 101, 99, 103, 104, 102]
    volatility = rolling_volatility(values, period=3)
    assert volatility[-1] is not None and volatility[-1] > 0
    assert volume_moving_average([10, 20, 30, 40], 2) == [None, 15.0, 25.0, 35.0]
    strength = relative_strength([100, 110, 120], [100, 105, 110])
    assert strength[0] == 0
    assert strength[-1] == pytest.approx(120 / 110 - 1)


def test_indicator_validation() -> None:
    with pytest.raises(ValueError, match="positive"):
        simple_moving_average([1, 2], 0)
    with pytest.raises(ValueError, match="same length"):
        average_true_range([1], [1, 2], [1])
    with pytest.raises(ValueError, match="less than"):
        moving_average_convergence_divergence([1, 2], fast=5, slow=3)
    assert math.isfinite(rolling_volatility([1, 2, 3, 4], 2)[-1] or 0)
