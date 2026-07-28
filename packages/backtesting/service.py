from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.backtesting.engine import BacktestEngine
from packages.backtesting.types import BacktestConfig, HistoricalBar
from packages.core.config import Settings
from packages.core.time import utc_now
from packages.database.models import (
    Asset,
    BacktestDailySnapshot,
    BacktestRun,
    BacktestTrade,
    PriceBar,
    Signal,
    SignalFactor,
    StrategyVersion,
)


def _historical_bar(bar: PriceBar, symbol: str) -> HistoricalBar:
    return HistoricalBar(
        id=bar.id,
        asset_id=bar.asset_id,
        data_source_id=bar.data_source_id,
        symbol=symbol,
        event_time=bar.event_time,
        publication_time=bar.publication_time,
        effective_time=bar.effective_time,
        retrieval_time=bar.retrieval_time,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,
    )


def run_backtest(
    session: Session,
    *,
    strategy_version_id: UUID,
    parameters: dict[str, object],
    config: BacktestConfig,
    start_time: datetime,
    end_time: datetime,
    settings: Settings,
) -> BacktestRun:
    version = session.get(StrategyVersion, strategy_version_id)
    if version is None:
        raise ValueError("strategy version was not found")
    strategy_type = version.strategy.strategy_type
    symbols = list(dict.fromkeys([*config.symbols, config.benchmark_symbol]))
    assets = {
        asset.symbol: asset
        for asset in session.scalars(select(Asset).where(Asset.symbol.in_(symbols))).all()
    }
    missing = sorted(set(symbols) - set(assets))
    if missing:
        raise ValueError(f"Unknown assets: {', '.join(missing)}")
    bars_by_symbol: dict[str, list[HistoricalBar]] = {}
    for symbol in symbols:
        asset = assets[symbol]
        bars = session.scalars(
            select(PriceBar)
            .where(
                PriceBar.asset_id == asset.id,
                PriceBar.event_time >= start_time,
                PriceBar.event_time <= end_time,
            )
            .order_by(PriceBar.event_time)
        ).all()
        bars_by_symbol[symbol] = [_historical_bar(bar, symbol) for bar in bars]
    if any(not bars_by_symbol[symbol] for symbol in symbols):
        empty = [symbol for symbol in symbols if not bars_by_symbol[symbol]]
        raise ValueError(f"No price history in range for: {', '.join(empty)}")

    result = BacktestEngine().run(
        bars_by_symbol={symbol: bars_by_symbol[symbol] for symbol in config.symbols},
        benchmark_bars=bars_by_symbol[config.benchmark_symbol],
        strategy_type=strategy_type,
        strategy_parameters=parameters,
        config=config,
    )
    run = BacktestRun(
        strategy_version_id=version.id,
        status="completed",
        asset_symbols=config.symbols,
        benchmark_symbol=config.benchmark_symbol,
        start_time=start_time,
        end_time=end_time,
        initial_cash=config.initial_cash,
        cash_balance=Decimal(str(result.metrics["cash_balance"])),
        final_equity=Decimal(str(result.metrics["final_equity"])),
        strategy_configuration=parameters,
        risk_configuration={
            "max_position_pct": str(config.max_position_pct),
            "max_total_exposure": str(config.max_total_exposure),
        },
        execution_assumptions=result.assumptions,
        source_data_identifiers=result.source_data_identifiers,
        data_source_identifiers=result.data_source_identifiers,
        metrics=result.metrics,
        application_version=settings.version,
        is_hypothetical=True,
        completed_at=utc_now(),
    )
    session.add(run)
    session.flush()
    session.add_all(
        [
            BacktestTrade(
                backtest_run_id=run.id,
                asset_id=trade.asset_id,
                source_price_bar_id=trade.source_price_bar_id,
                symbol=trade.symbol,
                side=trade.side,
                signal_time=trade.signal_time,
                execution_time=trade.execution_time,
                quantity=trade.quantity,
                price=trade.price,
                gross_value=trade.gross_value,
                fees=trade.fees,
                cash_after=trade.cash_after,
                reason=trade.reason,
            )
            for trade in result.trades
        ]
    )
    session.add_all(
        [
            BacktestDailySnapshot(
                backtest_run_id=run.id,
                event_time=snapshot.event_time,
                equity=snapshot.equity,
                cash=snapshot.cash,
                positions=snapshot.positions,
                cumulative_fees=snapshot.cumulative_fees,
                exposure=snapshot.exposure,
                drawdown=snapshot.drawdown,
                benchmark_value=snapshot.benchmark_value,
            )
            for snapshot in result.snapshots
        ]
    )
    for generated in result.signals:
        signal = Signal(
            backtest_run_id=run.id,
            strategy_version_id=version.id,
            asset_id=generated.asset_id,
            source_price_bar_id=generated.source_price_bar_id,
            generated_at=generated.generated_at,
            eligible_after=generated.eligible_after,
            direction=generated.direction,
            strength=generated.strength,
            explanation=generated.explanation,
        )
        session.add(signal)
        session.flush()
        session.add_all(
            [
                SignalFactor(signal_id=signal.id, name=name, value=value, metadata_json={})
                for name, value in generated.factors.items()
            ]
        )
    session.flush()
    return run
