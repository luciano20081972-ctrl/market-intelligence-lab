from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from statistics import mean, median
from typing import Any

import numpy as np
from scipy.stats import spearmanr  # type: ignore[import-untyped]


class EvaluationMode(StrEnum):
    PROSPECTIVE = "PROSPECTIVE"
    HISTORICAL_REPLAY = "HISTORICAL_REPLAY"
    FIXTURE = "FIXTURE"


class ForecastType(StrEnum):
    DIRECTIONAL = "DIRECTIONAL"
    PROBABILITY = "PROBABILITY"
    CONTINUOUS = "CONTINUOUS"
    INTERVAL = "INTERVAL"
    RANK = "RANK"
    SCENARIO_CONDITIONAL = "SCENARIO_CONDITIONAL"


class CalibrationState(StrEnum):
    UNCALIBRATED = "UNCALIBRATED"
    PRELIMINARY_CALIBRATION = "PRELIMINARY_CALIBRATION"
    CALIBRATED = "CALIBRATED"


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


@dataclass(frozen=True)
class FrozenForecast:
    id: str
    workspace_id: str
    target_definition: dict[str, Any]
    forecast_type: ForecastType
    forecast_value: Any
    evaluation_mode: EvaluationMode
    as_of_time: datetime
    target_start_time: datetime
    target_end_time: datetime
    outcome_eligible_time: datetime
    manifest: dict[str, Any]
    checksum: str
    locked_at: datetime | None = None
    supersedes_id: str | None = None

    def lock(self, at: datetime) -> FrozenForecast:
        if at > self.outcome_eligible_time:
            raise ValueError("forecast must be locked before outcome eligibility")
        if self.locked_at is not None:
            raise ValueError("forecast is already locked")
        return replace(self, locked_at=at)

    @property
    def state(self) -> str:
        return "LOCKED" if self.locked_at else "OPEN"


def create_forecast(**values: Any) -> FrozenForecast:
    mode = EvaluationMode(values["evaluation_mode"])
    kind = ForecastType(values["forecast_type"])
    if values["target_start_time"] < values["as_of_time"]:
        raise ValueError("target window cannot begin before the forecast as-of time")
    if values["outcome_eligible_time"] < values["target_end_time"]:
        raise ValueError("outcome eligibility cannot precede the target end")
    value = copy.deepcopy(values["forecast_value"])
    if kind is ForecastType.PROBABILITY and not 0 <= float(value) <= 1:
        raise ValueError("probability forecast must be bounded between zero and one")
    body = {key: value for key, value in values.items() if key not in {"id", "checksum"}}
    return FrozenForecast(
        id=str(values["id"]),
        workspace_id=str(values["workspace_id"]),
        target_definition=copy.deepcopy(values["target_definition"]),
        forecast_type=kind,
        forecast_value=value,
        evaluation_mode=mode,
        as_of_time=values["as_of_time"],
        target_start_time=values["target_start_time"],
        target_end_time=values["target_end_time"],
        outcome_eligible_time=values["outcome_eligible_time"],
        manifest=copy.deepcopy(values.get("manifest", {})),
        checksum=digest(body),
        supersedes_id=values.get("supersedes_id"),
    )


def observe_outcome(
    forecast: FrozenForecast, realized: Any, observed_at: datetime, source_manifest: dict[str, Any]
) -> dict[str, Any]:
    if forecast.locked_at is None:
        raise ValueError("forecast must be locked before an outcome can be observed")
    if observed_at < forecast.outcome_eligible_time:
        raise ValueError("outcome is not mature")
    body = {
        "forecast_id": forecast.id,
        "realized": realized,
        "observed_at": observed_at,
        "source_manifest": source_manifest,
    }
    return {
        **body,
        "evaluation_mode": forecast.evaluation_mode.value,
        "outcome_checksum": digest(body),
        "immutable": True,
    }


def score_forecast(
    kind: ForecastType | str, forecast: Any, realized: Any, *, alpha: float = 0.05
) -> dict[str, float | bool]:
    kind = ForecastType(kind)
    if kind in {ForecastType.DIRECTIONAL, ForecastType.SCENARIO_CONDITIONAL}:
        return {"directionally_correct": bool(float(forecast) * float(realized) > 0)}
    if kind is ForecastType.PROBABILITY:
        probability = min(1 - 1e-15, max(1e-15, float(forecast)))
        outcome = float(realized)
        return {
            "brier_score": (probability - outcome) ** 2,
            "log_loss": -(
                outcome * math.log(probability) + (1 - outcome) * math.log(1 - probability)
            ),
        }
    if kind is ForecastType.CONTINUOUS:
        error = float(forecast) - float(realized)
        return {"absolute_error": abs(error), "squared_error": error**2, "signed_bias": error}
    if kind is ForecastType.INTERVAL:
        lower, upper = map(float, forecast)
        actual = float(realized)
        width = upper - lower
        penalty = (2 / alpha) * (
            lower - actual if actual < lower else actual - upper if actual > upper else 0
        )
        return {
            "covered": lower <= actual <= upper,
            "interval_width": width,
            "interval_score": width + penalty,
        }
    predicted_values = np.asarray(forecast, dtype=float)
    actual_values = np.asarray(realized, dtype=float)
    correlation = spearmanr(predicted_values, actual_values).statistic
    return {"spearman_rank": float(correlation), "rank_ic": float(correlation)}


def aggregate_scores(
    records: Iterable[dict[str, Any]],
    *,
    mode: EvaluationMode | str,
    as_of: datetime | None = None,
    minimum_sample: int = 20,
) -> dict[str, Any]:
    selected = [
        r
        for r in records
        if r["evaluation_mode"] == str(EvaluationMode(mode).value)
        and (as_of is None or r["observed_at"] <= as_of)
    ]
    count = len(selected)
    status = (
        "INSUFFICIENT_SAMPLE"
        if count < minimum_sample
        else "PRELIMINARY"
        if count < 50
        else "ESTABLISHING"
        if count < 100
        else "USABLE"
    )
    briers = [float(r["brier_score"]) for r in selected if "brier_score" in r]
    return {
        "evaluation_mode": EvaluationMode(mode).value,
        "sample_count": count,
        "status": status,
        "mean_brier_score": mean(briers) if briers else None,
        "as_of_time": as_of,
        "methodology_version": "calibration-v1",
    }


def calibration_bins(
    probabilities: list[float], outcomes: list[int], bins: int = 10
) -> list[dict[str, Any]]:
    if len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes must have equal lengths")
    result = []
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        values = [
            (p, o)
            for p, o in zip(probabilities, outcomes, strict=True)
            if low <= p < high or (index == bins - 1 and p == 1)
        ]
        if values:
            result.append(
                {
                    "lower": low,
                    "upper": high,
                    "sample_count": len(values),
                    "expected_frequency": mean(p for p, _ in values),
                    "observed_frequency": mean(o for _, o in values),
                }
            )
    return result


def confidence_calibration(rows: list[dict[str, Any]], minimum_sample: int = 20) -> dict[str, Any]:
    rows = [r for r in rows if r["evaluation_mode"] == EvaluationMode.PROSPECTIVE.value]
    status = "INSUFFICIENT_SAMPLE" if len(rows) < minimum_sample else "USABLE"
    correlation = None
    if len(rows) >= 2:
        correlation = float(
            spearmanr([r["confidence"] for r in rows], [r["quality"] for r in rows]).statistic
        )
    return {
        "sample_count": len(rows),
        "status": status,
        "monotonicity": correlation,
        "semantics": "confidence_decomposition_not_event_probability",
    }


def eligibility(
    gates: dict[str, bool], calibration_state: CalibrationState | str, unresolved_critical: bool
) -> dict[str, Any]:
    failed = sorted(key for key, passed in gates.items() if not passed)
    if unresolved_critical:
        failed.append("unresolved_critical_skeptic_challenge")
    state = CalibrationState(calibration_state)
    return {
        "eligible": not failed,
        "failed_gates": failed,
        "calibration_state": state.value,
        "risk_tier": "STRICT_UNCALIBRATED"
        if state is CalibrationState.UNCALIBRATED
        else "STANDARD",
        "paper_only": True,
    }


def allocation_priority(
    components: dict[str, float], *, version: str = "paper-priority-v1"
) -> dict[str, Any]:
    weights = {
        "qualification": 0.25,
        "independence": 0.15,
        "reliability": 0.15,
        "confidence_quality": 0.15,
        "freshness": 0.1,
        "diversification": 0.1,
        "fragility_penalty": -0.04,
        "skeptic_penalty": -0.03,
        "scenario_penalty": -0.03,
    }
    score = sum(float(components.get(key, 0)) * weight for key, weight in weights.items())
    return {
        "value": round(max(0.0, min(1.0, score)), 6),
        "components": components,
        "weights": weights,
        "formula_version": version,
        "semantics": "paper_allocation_priority_not_expected_alpha",
    }


def construct_portfolio(
    scores: dict[str, float],
    *,
    method: str = "SCORE_CAPPED",
    max_position: float = 0.2,
    min_cash: float = 0.1,
) -> dict[str, Any]:
    if method not in {
        "EQUAL_WEIGHT",
        "SCORE_CAPPED",
        "VOLATILITY_SCALED",
        "RISK_PARITY",
        "MINIMUM_VARIANCE",
    }:
        raise ValueError("unsupported construction method")
    if not scores:
        return {"weights": {}, "cash_weight": 1.0, "method": method}
    raw = {
        key: 1.0 if method == "EQUAL_WEIGHT" else max(0.0, value) for key, value in scores.items()
    }
    total = sum(raw.values()) or 1.0
    investable = 1 - min_cash
    weights = {key: min(max_position, investable * value / total) for key, value in raw.items()}
    remaining = investable - sum(weights.values())
    uncapped = [key for key in weights if weights[key] < max_position]
    while remaining > 1e-9 and uncapped:
        add = remaining / len(uncapped)
        for key in list(uncapped):
            delta = min(add, max_position - weights[key])
            weights[key] += delta
            remaining -= delta
            if weights[key] >= max_position - 1e-9:
                uncapped.remove(key)
    return {
        "weights": {key: round(value, 8) for key, value in weights.items()},
        "cash_weight": round(1 - sum(weights.values()), 8),
        "method": method,
        "no_shorting": all(value >= 0 for value in weights.values()),
        "no_leverage": sum(weights.values()) <= 1.0,
    }


def research_risk(
    weights: dict[str, float],
    domains: dict[str, str],
    *,
    max_position: float = 0.2,
    max_domain: float = 0.4,
) -> dict[str, Any]:
    violations = [
        f"position:{key}" for key, value in weights.items() if value > max_position + 1e-9
    ]
    domain_weights: dict[str, float] = {}
    for asset, value in weights.items():
        domain_weights[domains.get(asset, "UNKNOWN")] = (
            domain_weights.get(domains.get(asset, "UNKNOWN"), 0) + value
        )
    violations.extend(
        f"information_domain:{key}"
        for key, value in domain_weights.items()
        if value > max_domain + 1e-9
    )
    return {
        "approved": not violations,
        "violations": violations,
        "information_domain_weights": domain_weights,
    }


def scenario_stress(
    weights: dict[str, float], shocks: dict[str, dict[str, float]], *, loss_limit: float = 0.15
) -> dict[str, Any]:
    results = {
        name: sum(weights.get(asset, 0) * effect for asset, effect in impacts.items())
        for name, impacts in shocks.items()
    }
    worst = min(results.values(), default=0.0)
    return {
        "results": results,
        "worst_return": worst,
        "approved": worst >= -loss_limit,
        "probabilities_assigned": False,
    }


def rebalance_orders(
    current: dict[str, float],
    target: dict[str, float],
    equity: float,
    prices: dict[str, float],
    plan_id: str,
) -> list[dict[str, Any]]:
    orders = []
    for asset in sorted(set(current) | set(target)):
        difference = target.get(asset, 0) - current.get(asset, 0)
        quantity = abs(difference * equity / prices[asset])
        if quantity > 1e-9:
            orders.append(
                {
                    "symbol": asset,
                    "side": "BUY" if difference > 0 else "SELL",
                    "quantity": round(quantity, 8),
                    "client_order_id": digest([plan_id, asset, round(difference, 10)])[:32],
                    "preview": True,
                    "paper_only": True,
                }
            )
    return orders


def portfolio_evaluation(equity: list[float], benchmark: list[float]) -> dict[str, Any]:
    returns = [equity[i] / equity[i - 1] - 1 for i in range(1, len(equity))]
    benchmark_return = benchmark[-1] / benchmark[0] - 1 if len(benchmark) > 1 else 0.0
    peaks = np.maximum.accumulate(equity)
    drawdown = min((np.asarray(equity) / peaks - 1).tolist(), default=0.0)
    return {
        "return": equity[-1] / equity[0] - 1 if len(equity) > 1 else 0.0,
        "benchmark_relative_return": (equity[-1] / equity[0] - 1) - benchmark_return
        if len(equity) > 1
        else -benchmark_return,
        "volatility": float(np.std(returns)) if returns else 0.0,
        "max_drawdown": drawdown,
        "median_period_return": median(returns) if returns else 0.0,
        "label": "SIMULATED / PAPER ONLY",
    }
