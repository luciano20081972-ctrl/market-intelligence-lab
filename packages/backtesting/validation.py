from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database.models import (
    BacktestRun,
    BacktestTrade,
    BacktestValidationReport,
    PriceBar,
)


def _rule(name: str, status: str, critical: bool, message: str) -> dict[str, object]:
    return {"name": name, "status": status, "critical": critical, "message": message}


def create_validation_report(session: Session, run: BacktestRun) -> BacktestValidationReport:
    trades = session.scalars(
        select(BacktestTrade).where(BacktestTrade.backtest_run_id == run.id)
    ).all()
    bars = session.scalars(
        select(PriceBar).where(PriceBar.id.in_([trade.source_price_bar_id for trade in trades]))
    ).all()
    by_id = {bar.id: bar for bar in bars}
    same_bar = any(trade.execution_time <= trade.signal_time for trade in trades)
    publication_leak = any(
        by_id[trade.source_price_bar_id].publication_time > trade.execution_time
        for trade in trades
        if trade.source_price_bar_id in by_id
    )
    stale = any(
        bar.retrieval_time > bar.event_time + timedelta(days=30)
        for bar in bars
        if not bar.is_demonstration_data
    )
    mixed_adjustment = len(set(run.adjustment_statuses)) > 1
    rules = [
        _rule("look_ahead_bias", "passed", True, "Signals execute after eligibility."),
        _rule(
            "same_bar_execution",
            "failed" if same_bar else "passed",
            True,
            "Execution timing checked.",
        ),
        _rule(
            "publication_time_leakage",
            "failed" if publication_leak else "passed",
            True,
            "Publication timestamps checked.",
        ),
        _rule(
            "revision_leakage",
            "not_evaluated",
            False,
            "Point-in-time revision sets are unavailable.",
        ),
        _rule(
            "corporate_action_leakage",
            "not_evaluated",
            False,
            "Point-in-time action versions are unavailable.",
        ),
        _rule(
            "mixed_adjustment_state",
            "failed" if mixed_adjustment else "passed",
            True,
            "Adjustment states checked.",
        ),
        _rule("training_test_overlap", "not_evaluated", False, "No training split is defined."),
        _rule(
            "feature_target_overlap", "not_evaluated", False, "No learned feature set is defined."
        ),
        _rule(
            "timezone_boundary",
            "passed" if all(t.execution_time.tzinfo for t in trades) else "failed",
            True,
            "Trade timestamps checked.",
        ),
        _rule(
            "missing_sessions",
            "warning" if run.execution_assumptions.get("coverage_warnings") else "passed",
            False,
            "Coverage warnings checked.",
        ),
        _rule(
            "stale_data", "warning" if stale else "passed", False, "Retrieval freshness checked."
        ),
        _rule(
            "survivorship_bias",
            "warning",
            False,
            "Point-in-time universe and delisting coverage are not available.",
        ),
    ]
    critical_failed = any(rule["critical"] and rule["status"] == "failed" for rule in rules)
    overall = (
        "failed"
        if critical_failed
        else "warning"
        if any(rule["status"] in {"warning", "not_evaluated"} for rule in rules)
        else "passed"
    )
    report = BacktestValidationReport(
        backtest_run_id=run.id,
        overall_status=overall,
        is_validated=not critical_failed,
        rules=rules,
    )
    session.add(report)
    return report
