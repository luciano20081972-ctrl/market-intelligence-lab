from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_DOWN, Decimal

from packages.backtesting.metrics import calculate_metrics
from packages.backtesting.types import (
    BacktestConfig,
    BacktestResult,
    DailySnapshot,
    GeneratedSignal,
    HistoricalBar,
    SimulatedTrade,
)
from packages.strategies.registry import get_strategy_definition

MONEY = Decimal("0.000001")
SHARES = Decimal("0.00000001")
RISK_TARGET_BUFFER = Decimal("0.99")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY)


@dataclass
class _Position:
    quantity: Decimal = Decimal("0")
    average_cost: Decimal = Decimal("0")
    opened_index: int = 0


@dataclass(frozen=True)
class _PendingTargets:
    execution_index: int
    signal_index: int
    signal_time: datetime
    updates: dict[str, float]
    reasons: dict[str, str]


class BacktestEngine:
    """Bar-based simulator with shared cash and signals delayed to later bars."""

    def run(
        self,
        *,
        bars_by_symbol: dict[str, list[HistoricalBar]],
        benchmark_bars: list[HistoricalBar],
        strategy_type: str,
        strategy_parameters: dict[str, object],
        config: BacktestConfig,
    ) -> BacktestResult:
        definition = get_strategy_definition(strategy_type)
        parameters = definition.parameters_model.model_validate(strategy_parameters)
        ordered = {
            symbol: sorted(bars_by_symbol[symbol], key=lambda bar: bar.event_time)
            for symbol in config.symbols
        }
        if any(not bars for bars in ordered.values()):
            raise ValueError("every selected symbol must have price history")
        common_times = set.intersection(
            *(set(bar.event_time for bar in bars) for bars in ordered.values())
        )
        benchmark_by_time = {bar.event_time: bar for bar in benchmark_bars}
        times = sorted(time for time in common_times if time in benchmark_by_time)
        if len(times) < config.execution_delay + 2:
            raise ValueError("not enough aligned price bars for the configured delay")
        aligned = {
            symbol: {bar.event_time: bar for bar in bars} for symbol, bars in ordered.items()
        }
        result = BacktestResult()
        result.source_data_identifiers = sorted(
            {str(aligned[symbol][time].id) for symbol in config.symbols for time in times}
            | {str(benchmark_by_time[time].id) for time in times}
        )
        result.data_source_identifiers = sorted(
            {
                str(aligned[symbol][time].data_source_id)
                for symbol in config.symbols
                for time in times
            }
            | {str(benchmark_by_time[time].data_source_id) for time in times}
        )
        result.assumptions = {
            "execution_price": "next eligible bar open after configured delay",
            "long_only": True,
            "fractional_shares": True,
            "commission": str(config.commission),
            "spread_bps": str(config.spread_bps),
            "slippage_bps": str(config.slippage_bps),
            "execution_delay": config.execution_delay,
            "publication_rule": "signal time is max(publication_time, effective_time)",
            "risk_limit_handling": (
                "targets use a 1% safety buffer; observed close breaches rebalance "
                "at the next eligible bar open"
            ),
        }
        cash = config.initial_cash
        positions = {symbol: _Position() for symbol in config.symbols}
        targets = {symbol: 0.0 for symbol in config.symbols}
        pending: list[_PendingTargets] = []
        cumulative_fees = Decimal("0")
        peak_equity = config.initial_cash
        benchmark_start = benchmark_by_time[times[0]].close
        close_history: dict[str, list[float]] = {symbol: [] for symbol in config.symbols}

        for index, event_time in enumerate(times):
            bars = {symbol: aligned[symbol][event_time] for symbol in config.symbols}
            due = [item for item in pending if item.execution_index == index]
            if (
                not due
                and result.snapshots
                and self._risk_limit_breached(result.snapshots[-1], config)
            ):
                trades, cash, fees = self._rebalance(
                    index=index,
                    bars=bars,
                    positions=positions,
                    targets=targets,
                    cash=cash,
                    signal_time=result.snapshots[-1].event_time,
                    reasons={symbol: "Risk-limit rebalance" for symbol in config.symbols},
                    config=config,
                    rejections=result.rejections,
                )
                result.trades.extend(trades)
                cumulative_fees += fees
            for item in due:
                targets.update(item.updates)
                trades, cash, fees = self._rebalance(
                    index=index,
                    bars=bars,
                    positions=positions,
                    targets=targets,
                    cash=cash,
                    signal_time=item.signal_time,
                    reasons=item.reasons,
                    config=config,
                    rejections=result.rejections,
                )
                result.trades.extend(trades)
                cumulative_fees += fees
            pending = [item for item in pending if item.execution_index != index]

            market_value = sum(
                positions[symbol].quantity * bars[symbol].close for symbol in config.symbols
            )
            equity = _money(cash + market_value)
            peak_equity = max(peak_equity, equity)
            drawdown = equity / peak_equity - 1 if peak_equity else Decimal("0")
            exposure = market_value / equity if equity else Decimal("0")
            benchmark_value = (
                config.initial_cash * benchmark_by_time[event_time].close / benchmark_start
            )
            result.snapshots.append(
                DailySnapshot(
                    event_time=event_time,
                    equity=equity,
                    cash=_money(cash),
                    positions={
                        symbol: {
                            "quantity": str(position.quantity),
                            "average_cost": str(position.average_cost),
                            "close": str(bars[symbol].close),
                            "value": str(_money(position.quantity * bars[symbol].close)),
                        }
                        for symbol, position in positions.items()
                        if position.quantity > 0
                    },
                    cumulative_fees=_money(cumulative_fees),
                    exposure=exposure,
                    drawdown=drawdown,
                    benchmark_value=_money(benchmark_value),
                )
            )

            updates: dict[str, float] = {}
            reasons: dict[str, str] = {}
            signal_times: list[datetime] = []
            for symbol in config.symbols:
                bar = bars[symbol]
                close_history[symbol].append(float(bar.close))
                decision = definition.generate(close_history[symbol], index, parameters)
                if decision.target_weight is None:
                    continue
                updates[symbol] = decision.target_weight
                reasons[symbol] = decision.explanation
                signal_time = max(bar.publication_time, bar.effective_time)
                signal_times.append(signal_time)
                result.signals.append(
                    GeneratedSignal(
                        asset_id=bar.asset_id,
                        source_price_bar_id=bar.id,
                        symbol=symbol,
                        generated_at=signal_time,
                        eligible_after=signal_time,
                        direction=decision.direction,
                        strength=Decimal(str(decision.strength)),
                        explanation=decision.explanation,
                        factors={
                            name: Decimal(str(value)) for name, value in decision.factors.items()
                        },
                    )
                )
            if updates:
                execution_index = self._eligible_execution_index(
                    times, index, max(signal_times), config.execution_delay
                )
                if execution_index is not None:
                    pending.append(
                        _PendingTargets(
                            execution_index=execution_index,
                            signal_index=index,
                            signal_time=max(signal_times),
                            updates=updates,
                            reasons=reasons,
                        )
                    )

        result.metrics = calculate_metrics(
            result.snapshots, result.trades, float(config.initial_cash)
        )
        return result

    @staticmethod
    def _risk_limit_breached(snapshot: DailySnapshot, config: BacktestConfig) -> bool:
        """Schedule a next-bar rebalance after an observed close breaches a limit."""
        exposure_limit = config.max_total_exposure * RISK_TARGET_BUFFER
        position_limit = config.max_position_pct * RISK_TARGET_BUFFER
        if snapshot.exposure > exposure_limit:
            return True
        if not snapshot.equity:
            return False
        return any(
            Decimal(position["value"]) / snapshot.equity > position_limit
            for position in snapshot.positions.values()
        )

    @staticmethod
    def _eligible_execution_index(
        times: list[datetime], signal_index: int, signal_time: datetime, delay: int
    ) -> int | None:
        candidate = signal_index + delay
        while candidate < len(times) and times[candidate] <= signal_time:
            candidate += 1
        return candidate if candidate < len(times) else None

    def _rebalance(
        self,
        *,
        index: int,
        bars: dict[str, HistoricalBar],
        positions: dict[str, _Position],
        targets: dict[str, float],
        cash: Decimal,
        signal_time: datetime,
        reasons: dict[str, str],
        config: BacktestConfig,
        rejections: list[str],
    ) -> tuple[list[SimulatedTrade], Decimal, Decimal]:
        equity = cash + sum(positions[symbol].quantity * bars[symbol].open for symbol in positions)
        position_limit = config.max_position_pct * RISK_TARGET_BUFFER
        exposure_limit = config.max_total_exposure * RISK_TARGET_BUFFER
        capped = {
            symbol: min(Decimal(str(max(weight, 0.0))), position_limit)
            for symbol, weight in targets.items()
        }
        total = sum(capped.values(), Decimal("0"))
        if total > exposure_limit:
            scale = exposure_limit / total
            capped = {symbol: weight * scale for symbol, weight in capped.items()}
        trades: list[SimulatedTrade] = []
        total_fees = Decimal("0")
        desired_quantities = {
            symbol: ((equity * weight) / bars[symbol].open).quantize(SHARES, rounding=ROUND_DOWN)
            for symbol, weight in capped.items()
        }
        for symbol in sorted(positions):
            current = positions[symbol]
            desired = desired_quantities[symbol]
            if desired >= current.quantity:
                continue
            quantity = current.quantity - desired
            trade, cash, fee = self._execute(
                index=index,
                bar=bars[symbol],
                position=current,
                side="sell",
                quantity=quantity,
                cash=cash,
                signal_time=signal_time,
                reason=reasons.get(symbol, "Portfolio rebalance"),
                config=config,
            )
            trades.append(trade)
            total_fees += fee
        for symbol in sorted(positions):
            current = positions[symbol]
            desired = desired_quantities[symbol]
            if desired <= current.quantity:
                continue
            quantity = desired - current.quantity
            estimated_price = self._execution_price(bars[symbol].open, "buy", config)
            required = quantity * estimated_price + config.commission
            if required > cash:
                affordable = max(cash - config.commission, Decimal("0")) / estimated_price
                quantity = affordable.quantize(SHARES, rounding=ROUND_DOWN)
            if quantity <= 0:
                rejections.append(f"{bars[symbol].symbol}: insufficient shared cash")
                continue
            trade, cash, fee = self._execute(
                index=index,
                bar=bars[symbol],
                position=current,
                side="buy",
                quantity=quantity,
                cash=cash,
                signal_time=signal_time,
                reason=reasons.get(symbol, "Portfolio rebalance"),
                config=config,
            )
            trades.append(trade)
            total_fees += fee
        return trades, cash, total_fees

    def _execute(
        self,
        *,
        index: int,
        bar: HistoricalBar,
        position: _Position,
        side: str,
        quantity: Decimal,
        cash: Decimal,
        signal_time: datetime,
        reason: str,
        config: BacktestConfig,
    ) -> tuple[SimulatedTrade, Decimal, Decimal]:
        price = self._execution_price(bar.open, side, config)
        gross = _money(quantity * price)
        fee = config.commission
        realized = Decimal("0")
        holding_days = 0
        if side == "buy":
            previous_cost = position.quantity * position.average_cost
            cash -= gross + fee
            if position.quantity == 0:
                position.opened_index = index
            position.quantity += quantity
            position.average_cost = (previous_cost + gross + fee) / position.quantity
        else:
            cash += gross - fee
            realized = gross - fee - quantity * position.average_cost
            holding_days = max(index - position.opened_index, 0)
            position.quantity -= quantity
            if position.quantity <= SHARES:
                position.quantity = Decimal("0")
                position.average_cost = Decimal("0")
        trade = SimulatedTrade(
            asset_id=bar.asset_id,
            source_price_bar_id=bar.id,
            symbol=bar.symbol,
            side=side,
            signal_time=signal_time,
            execution_time=bar.event_time,
            quantity=quantity,
            price=price,
            gross_value=gross,
            fees=fee,
            cash_after=_money(cash),
            reason=reason,
            realized_pnl=_money(realized),
            holding_days=holding_days,
        )
        return trade, cash, fee

    @staticmethod
    def _execution_price(base: Decimal, side: str, config: BacktestConfig) -> Decimal:
        friction = (config.spread_bps / 2 + config.slippage_bps) / Decimal("10000")
        multiplier = Decimal("1") + friction if side == "buy" else Decimal("1") - friction
        return (base * multiplier).quantize(SHARES)
