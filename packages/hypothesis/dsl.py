from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

ALLOWED_OPERATIONS = frozenset(
    {
        "lag",
        "difference",
        "ratio",
        "rolling_mean",
        "rolling_std",
        "rolling_change",
        "weighted_average",
        "zscore",
        "percentile",
        "rank",
        "winsorize",
        "cross_section_rank",
    }
)
MAX_LOOKBACK = 2520


def validate_feature_spec(specification: dict[str, Any]) -> None:
    required = {
        "feature_key",
        "required_datasets",
        "required_graph_paths",
        "transformations",
        "lookback",
        "lag",
        "missing_data_policy",
        "normalization",
        "temporal_policy",
    }
    missing = sorted(required - specification.keys())
    if missing:
        raise ValueError(f"feature specification is missing: {', '.join(missing)}")
    lookback = specification["lookback"]
    lag = specification["lag"]
    if not isinstance(lookback, int) or not 1 <= lookback <= MAX_LOOKBACK:
        raise ValueError("lookback must be between 1 and 2520 observations")
    if not isinstance(lag, int) or not 0 <= lag <= MAX_LOOKBACK:
        raise ValueError("lag must be between 0 and 2520 observations")
    temporal_policy = specification["temporal_policy"]
    if not isinstance(temporal_policy, dict) or not temporal_policy.get(
        "simulation_eligible_only", False
    ):
        raise ValueError("feature specifications must require simulation-eligible inputs")
    transformations = specification["transformations"]
    if not isinstance(transformations, list) or not transformations:
        raise ValueError("at least one declarative transformation is required")
    for operation in transformations:
        if not isinstance(operation, dict) or operation.get("operation") not in ALLOWED_OPERATIONS:
            raise ValueError("feature specification contains an unsupported operation")
        _validate_operation(operation)


def _validate_operation(operation: dict[str, Any]) -> None:
    name = str(operation["operation"])
    if name in {"lag", "difference", "rolling_mean", "rolling_std", "rolling_change"}:
        periods = operation.get("periods", operation.get("window"))
        if not isinstance(periods, int) or not 1 <= periods <= MAX_LOOKBACK:
            raise ValueError(f"{name} requires a bounded positive period/window")
    if name == "winsorize":
        lower, upper = operation.get("lower", 0.01), operation.get("upper", 0.99)
        if not 0 <= lower < upper <= 1:
            raise ValueError("winsorize bounds must satisfy 0 <= lower < upper <= 1")
    if name == "percentile":
        percentile = operation.get("value")
        if not isinstance(percentile, (int, float)) or not 0 <= percentile <= 100:
            raise ValueError("percentile must be between 0 and 100")
    if name == "weighted_average":
        weights = operation.get("weights")
        if (
            not isinstance(weights, list)
            or not weights
            or not all(isinstance(item, (int, float)) for item in weights)
        ):
            raise ValueError("weighted_average requires numeric weights")


def execute_operations(
    values: Sequence[float], transformations: Sequence[dict[str, Any]]
) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    for operation in transformations:
        _validate_operation(operation)
        name = str(operation["operation"])
        if name == "lag":
            result = _lag(result, int(operation["periods"]))
        elif name == "difference":
            periods = int(operation["periods"])
            result = result - _lag(result, periods)
        elif name == "ratio":
            denominator = np.asarray(operation.get("denominator", []), dtype=float)
            if denominator.shape != result.shape:
                raise ValueError("ratio denominator must match input shape")
            result = np.divide(
                result,
                denominator,
                out=np.full(result.shape, np.nan),
                where=denominator != 0,
            )
        elif name in {"rolling_mean", "rolling_std", "rolling_change"}:
            raw_window = operation.get("window", operation.get("periods", 1))
            result = _rolling(result, int(raw_window), name)
        elif name == "weighted_average":
            weights = np.asarray(operation["weights"], dtype=float)
            if len(weights) != len(result):
                raise ValueError("weighted_average weights must match input length")
            result = np.asarray([float(np.average(result, weights=weights))])
        elif name == "zscore":
            standard_deviation = float(np.nanstd(result))
            result = (
                np.zeros_like(result)
                if standard_deviation == 0
                else (result - float(np.nanmean(result))) / standard_deviation
            )
        elif name == "percentile":
            result = np.asarray([float(np.nanpercentile(result, float(operation["value"])))])
        elif name in {"rank", "cross_section_rank"}:
            order = np.argsort(np.argsort(result, kind="stable"), kind="stable")
            result = order.astype(float) + 1.0
        elif name == "winsorize":
            lower = float(np.nanquantile(result, float(operation.get("lower", 0.01))))
            upper = float(np.nanquantile(result, float(operation.get("upper", 0.99))))
            result = np.clip(result, lower, upper)
    return result


def _lag(values: np.ndarray, periods: int) -> np.ndarray:
    result = np.full(values.shape, np.nan)
    result[periods:] = values[:-periods]
    return result


def _rolling(values: np.ndarray, window: int, operation: str) -> np.ndarray:
    result = np.full(values.shape, np.nan)
    for index in range(window - 1, len(values)):
        current = values[index - window + 1 : index + 1]
        if operation == "rolling_mean":
            result[index] = float(np.nanmean(current))
        elif operation == "rolling_std":
            result[index] = float(np.nanstd(current))
        else:
            result[index] = current[-1] - current[0]
    return result
