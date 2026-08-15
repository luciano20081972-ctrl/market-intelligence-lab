from __future__ import annotations

import importlib.metadata
import math
from statistics import mean, pvariance
from typing import Any

from packages.upstream.protocols import (
    UpstreamCapability,
    UpstreamHealthReport,
    UpstreamVersionInfo,
)

SUPPORTED_MODELS = frozenset(
    {
        "mean_risk",
        "minimum_variance",
        "maximum_sharpe",
        "risk_parity",
        "cvar",
        "efficient_frontier",
        "black_litterman",
    }
)


class SkfolioOptimizerAdapter:
    def health(self) -> UpstreamHealthReport:
        try:
            version = importlib.metadata.version("skfolio")
        except importlib.metadata.PackageNotFoundError:
            version = None
        return UpstreamHealthReport(
            status="available" if version else "fixture_only",
            available=True,
            capabilities=tuple(
                UpstreamCapability(model, model.replace("_", " ").title(), True)
                for model in sorted(SUPPORTED_MODELS)
            ),
            version=UpstreamVersionInfo("skfolio", "1.0", version or "0.20.1-fixture", None),
            message=(
                "Deterministic constrained foundation available; skfolio dependency is optional"
            ),
        )

    def optimize(
        self,
        returns: dict[str, tuple[float, ...]],
        *,
        model: str,
        allow_short: bool = False,
        allow_leverage: bool = False,
    ) -> dict[str, Any]:
        if model not in SUPPORTED_MODELS:
            raise ValueError("Unsupported optimization model")
        if allow_short or allow_leverage:
            raise ValueError("Short positions and leverage are disabled in this foundation")
        if len(returns) < 2:
            raise ValueError("At least two assets are required")
        lengths = {len(values) for values in returns.values()}
        if len(lengths) != 1 or not lengths or next(iter(lengths)) < 3:
            raise ValueError("Aligned return series with at least three observations are required")
        if any(any(not math.isfinite(value) for value in values) for values in returns.values()):
            raise ValueError("Return series cannot contain NaN or infinity")
        variances = {symbol: max(pvariance(values), 1e-12) for symbol, values in returns.items()}
        scores = (
            {symbol: 1 / value for symbol, value in variances.items()}
            if model in {"minimum_variance", "risk_parity", "cvar"}
            else {
                symbol: max(mean(returns[symbol]), 0.0) / math.sqrt(value)
                for symbol, value in variances.items()
            }
        )
        if not any(scores.values()):
            scores = {symbol: 1.0 for symbol in returns}
        total = sum(scores.values())
        weights = {symbol: score / total for symbol, score in scores.items()}
        if any(weight < 0 for weight in weights.values()) or sum(weights.values()) > 1.0000001:
            raise RuntimeError("Optimizer produced invalid constrained weights")
        portfolio_returns = [
            sum(weights[symbol] * values[index] for symbol, values in returns.items())
            for index in range(next(iter(lengths)))
        ]
        return {
            "model": model,
            "weights": weights,
            "objective_values": {"expected_return": mean(portfolio_returns)},
            "risk_metrics": {
                "volatility": math.sqrt(pvariance(portfolio_returns)),
                "stress_loss": min(portfolio_returns),
            },
            "warnings": ["Foundation adapter uses deterministic compatibility calculations"],
            "optimizer_version": self.health().version.library_version,
            "random_seed": 0,
        }
