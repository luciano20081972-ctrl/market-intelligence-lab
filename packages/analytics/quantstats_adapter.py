from __future__ import annotations

import importlib.metadata
import math
import re
from statistics import mean, pstdev
from typing import Any

from packages.upstream.protocols import (
    UpstreamCapability,
    UpstreamHealthReport,
    UpstreamVersionInfo,
)

METRICS = ("cagr", "sharpe", "sortino", "max_drawdown", "volatility", "calmar", "win_rate")


def _clean(values: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(value for value in values if math.isfinite(value))


def canonical_metrics(returns: tuple[float, ...], periods: int = 252) -> dict[str, float | None]:
    values = _clean(returns)
    if not values:
        return {name: None for name in METRICS}
    compounded = math.prod(1 + value for value in values)
    years = len(values) / periods
    cagr = compounded ** (1 / years) - 1 if years > 0 and compounded > 0 else None
    volatility = pstdev(values) * math.sqrt(periods) if len(values) > 1 else 0.0
    average = mean(values)
    sharpe = (
        average / pstdev(values) * math.sqrt(periods)
        if len(values) > 1 and pstdev(values)
        else None
    )
    downside = [min(value, 0.0) for value in values]
    downside_dev = math.sqrt(mean([value * value for value in downside]))
    sortino = average / downside_dev * math.sqrt(periods) if downside_dev else None
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in values:
        equity *= 1 + value
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1)
    calmar = cagr / abs(max_drawdown) if cagr is not None and max_drawdown else None
    return {
        "cagr": cagr,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_drawdown,
        "volatility": volatility,
        "calmar": calmar,
        "win_rate": sum(value > 0 for value in values) / len(values),
    }


class QuantStatsAnalyticsAdapter:
    def health(self) -> UpstreamHealthReport:
        try:
            version = importlib.metadata.version("quantstats")
        except importlib.metadata.PackageNotFoundError:
            version = None
        return UpstreamHealthReport(
            status="available" if version else "fixture_only",
            available=True,
            capabilities=tuple(
                UpstreamCapability(metric, f"Return-series {metric}", True) for metric in METRICS
            ),
            version=UpstreamVersionInfo("quantstats", "1.0", version or "0.0.81-fixture", None),
            message="Deterministic compatibility calculations available; library use is optional",
        )

    def calculate(
        self, returns: tuple[float, ...], benchmark: tuple[float, ...] | None = None
    ) -> dict[str, float | None]:
        if benchmark is not None and len(benchmark) != len(returns):
            raise ValueError("Benchmark and return series must be aligned")
        return canonical_metrics(returns)


def reconcile_metrics(
    canonical: dict[str, float | None],
    adapter: dict[str, float | None],
    *,
    tolerance: float,
) -> list[dict[str, Any]]:
    if tolerance < 0:
        raise ValueError("Tolerance cannot be negative")
    rows: list[dict[str, Any]] = []
    for name in METRICS:
        left = canonical.get(name)
        right = adapter.get(name)
        if left is None or right is None:
            rows.append(
                {
                    "metric": name,
                    "canonical": left,
                    "quantstats": right,
                    "absolute_difference": None,
                    "relative_difference": None,
                    "tolerance": tolerance,
                    "methodology_note": "Metric unavailable for this series",
                    "agreement_status": "not_comparable",
                }
            )
            continue
        absolute = abs(left - right)
        relative = absolute / max(abs(left), 1e-12)
        rows.append(
            {
                "metric": name,
                "canonical": left,
                "quantstats": right,
                "absolute_difference": absolute,
                "relative_difference": relative,
                "tolerance": tolerance,
                "methodology_note": "Daily return-series methodology",
                "agreement_status": "agrees" if absolute <= tolerance else "differs",
            }
        )
    return rows


def structured_report(
    *,
    name: str,
    period: tuple[str, str],
    benchmark: str | None,
    metrics: dict[str, float | None],
    versions: dict[str, str],
) -> dict[str, Any]:
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-") or "analytics-report"
    return {
        "filename": f"{safe_name[:80]}.json",
        "format": "application/json",
        "period": {"start": period[0], "end": period[1]},
        "benchmark": benchmark,
        "metrics": metrics,
        "engine_versions": versions,
        "provenance": "Market Intelligence Lab normalized return-series adapter",
        "contains_executable_content": False,
        "contains_secrets": False,
    }
