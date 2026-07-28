import pytest
from pydantic import BaseModel

from packages.strategies.registry import (
    STRATEGY_DEFINITIONS,
    get_strategy_definition,
    validate_strategy_parameters,
)


def test_all_seven_transparent_strategies_are_registered() -> None:
    assert set(STRATEGY_DEFINITIONS) == {
        "buy_and_hold",
        "moving_average_crossover",
        "momentum",
        "mean_reversion",
        "rsi_threshold",
        "volatility_breakout",
        "equal_weight_rebalance",
    }
    assert all(definition.calculation_notes for definition in STRATEGY_DEFINITIONS.values())


def test_strategy_parameter_validation_and_unknown_fields() -> None:
    with pytest.raises(ValueError, match="short_window"):
        validate_strategy_parameters(
            "moving_average_crossover", {"short_window": 50, "long_window": 20}
        )
    with pytest.raises(ValueError, match="extra"):
        validate_strategy_parameters("buy_and_hold", {"python": "print('unsafe')"})
    with pytest.raises(ValueError, match="Unknown strategy"):
        get_strategy_definition("arbitrary_python")


def test_strategy_signals_are_deterministic() -> None:
    definition = get_strategy_definition("momentum")
    parameters: BaseModel = definition.parameters_model.model_validate(
        {"lookback": 3, "minimum_return": 0}
    )
    closes = [100.0, 101.0, 102.0, 110.0]
    first = definition.generate(closes, 3, parameters)
    second = definition.generate(closes, 3, parameters)
    assert first == second
    assert first.direction == "long"
    assert first.factors["momentum_return"] == pytest.approx(0.1)


def test_strategy_api_lists_versioned_builtins(client: object) -> None:
    response = client.get("/api/v1/strategies")  # type: ignore[attr-defined]
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 7
    assert all(item["latest_version"]["version"] == 1 for item in body["items"])
    assert all(item["latest_version"]["parameter_schema"] for item in body["items"])
