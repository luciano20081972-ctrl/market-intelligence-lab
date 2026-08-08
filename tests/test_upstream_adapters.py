from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import pytest

from packages.analytics.quantstats_adapter import (
    QuantStatsAnalyticsAdapter,
    canonical_metrics,
    reconcile_metrics,
    structured_report,
)
from packages.external_engines import LeanAdapter, LeanBacktestRequest
from packages.optimization import SkfolioOptimizerAdapter

RETURNS = (0.01, -0.005, 0.007, 0.002, -0.001, 0.004)


def test_quantstats_reconciliation_and_tolerance() -> None:
    canonical = canonical_metrics(RETURNS)
    adapter = QuantStatsAnalyticsAdapter().calculate(RETURNS)
    rows = reconcile_metrics(canonical, adapter, tolerance=1e-12)
    assert all(row["agreement_status"] in {"agrees", "not_comparable"} for row in rows)
    changed = dict(adapter)
    changed["volatility"] = float(changed["volatility"] or 0) + 1
    assert next(
        row for row in reconcile_metrics(canonical, changed, tolerance=0.01)
        if row["metric"] == "volatility"
    )["agreement_status"] == "differs"


def test_quantstats_empty_short_nan_and_benchmark_alignment() -> None:
    assert canonical_metrics(())["cagr"] is None
    assert canonical_metrics((0.01,))["volatility"] == 0
    assert canonical_metrics((0.01, math.nan, 0.02))["win_rate"] == 1
    with pytest.raises(ValueError, match="aligned"):
        QuantStatsAnalyticsAdapter().calculate(RETURNS, (0.1,))


def test_structured_report_sanitizes_filename_and_has_provenance() -> None:
    report = structured_report(
        name="../../unsafe<script>",
        period=("2026-01-01", "2026-02-01"),
        benchmark="SPY",
        metrics=canonical_metrics(RETURNS),
        versions={"canonical": "0.6.0", "quantstats": "0.0.81"},
    )
    assert "/" not in report["filename"]
    assert report["contains_executable_content"] is False
    assert report["contains_secrets"] is False


def test_optimizer_is_deterministic_constrained_and_stress_reports() -> None:
    returns = {"AAA": RETURNS, "BBB": tuple(reversed(RETURNS))}
    adapter = SkfolioOptimizerAdapter()
    first = adapter.optimize(returns, model="minimum_variance")
    second = adapter.optimize(returns, model="minimum_variance")
    assert first == second
    assert sum(first["weights"].values()) == pytest.approx(1)
    assert all(0 <= value <= 1 for value in first["weights"].values())
    assert first["risk_metrics"]["stress_loss"] <= 0


def test_optimizer_rejects_infeasible_risky_or_unseparated_inputs() -> None:
    adapter = SkfolioOptimizerAdapter()
    values = {"AAA": RETURNS, "BBB": tuple(reversed(RETURNS))}
    with pytest.raises(ValueError, match="Short positions"):
        adapter.optimize(values, model="mean_risk", allow_short=True)
    with pytest.raises(ValueError, match="Short positions"):
        adapter.optimize(values, model="mean_risk", allow_leverage=True)
    with pytest.raises(ValueError, match="Aligned"):
        adapter.optimize({"AAA": (0.1,), "BBB": (0.2, 0.3)}, model="cvar")
    with pytest.raises(ValueError, match="NaN"):
        adapter.optimize({"AAA": (0.1, 0.2, math.nan), "BBB": (0.2, 0.1, 0.0)}, model="cvar")


def _lean_request(**changes: object) -> LeanBacktestRequest:
    values = {
        "strategy": "buy_and_hold",
        "symbols": ("AAPL",),
        "start": date(2025, 1, 1),
        "end": date(2025, 12, 31),
        "initial_cash": Decimal("10000"),
        "fee_per_order": Decimal("1"),
        "slippage_bps": Decimal("5"),
        "live_mode": False,
    }
    values.update(changes)
    return LeanBacktestRequest(**values)  # type: ignore[arg-type]


def test_lean_unavailable_fixture_manifest_and_comparison() -> None:
    adapter = LeanAdapter("definitely-not-installed")
    assert adapter.health().available is False
    result = adapter.fixture_run(_lean_request())
    assert result["status"] == "fixture_completed"
    assert result["manifest"]["live_mode"] is False
    assert result["manifest"]["brokerage_credentials"] is False
    assert result["comparison"]["difference"] == "2.50"
    assert len(result["request_checksum"]) == 64


def test_lean_rejects_live_invalid_and_external_execution() -> None:
    adapter = LeanAdapter()
    with pytest.raises(ValueError, match="live-trading"):
        adapter.fixture_run(_lean_request(live_mode=True))
    with pytest.raises(ValueError, match="symbols"):
        adapter.fixture_run(_lean_request(symbols=("BAD/SYMBOL",)))
    with pytest.raises(RuntimeError, match="disabled"):
        adapter.run({})
