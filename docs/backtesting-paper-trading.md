# Backtesting and paper trading

## Classification

Every strategy result, backtest, portfolio, order, and fill is hypothetical. The system has no broker adapter, credential field, real-order endpoint, margin, options, short selling, or autonomous execution. Stored synthetic daily bars are not live prices.

## Strategies and indicators

The built-in catalog contains buy and hold, moving-average crossover, momentum, mean reversion, RSI threshold, volatility breakout, and equal-weight rebalance. Each strategy has an immutable version, strict JSON parameters, generated parameter schema, calculation notes, and explainable signal factors. Arbitrary executable code is never accepted.

Indicators are pure deterministic functions: SMA, EMA, RSI, MACD, ATR, daily/cumulative return, rolling volatility, volume average, relative strength, and rolling drawdown. Invalid periods or insufficient history produce explicit validation errors or unavailable values rather than guessed output.

## Backtest timing and execution

Bars are aligned by UTC event time. A signal time is the later of its source bar publication and effective time. Execution occurs at the open of a later eligible bar after the configured delay; the engine never executes on the signal bar. All assets share one cash account, sells run before buys, and symbols are ordered deterministically.

The engine is long-only and supports fractional shares. Target weights use the configured maximum position and total exposure with a 1% sizing safety buffer. An observed close that drifts above the buffered risk target schedules a rebalance at the next bar open. This cannot prevent a price gap from temporarily crossing a configured percentage.

Buy and sell prices include half-spread plus slippage; every execution includes the configured commission. Results store exact source price-bar and data-source identifiers, the strategy version/configuration, application version, risk controls, and execution assumptions. Metrics include total and annualized return, volatility, Sharpe and Sortino ratios, maximum drawdown, Calmar ratio, benchmark return, alpha, beta, win rate, profit factor, trade count, exposure, turnover, fees, and holding period.

## Simulated order rules

- Market orders fill from the stored bar open plus configured friction.
- Buy limits fill at the open when it is at or below the limit, otherwise at the limit on an intrabar low touch. Sell limits use the symmetric rule. Friction never violates the limit.
- Buy stops trigger on a high touch and sell stops on a low touch. A marketable gap uses the less favorable open; an intrabar trigger uses the stop threshold before friction.
- Stop-limit orders retain their triggered state if the stop is touched but the limit is not marketable. They remain cancellable.
- A `(portfolio_id, client_order_id)` uniqueness constraint makes a retry return the original simulated order without a second fill.

Each preview and submission evaluates enabled rules for maximum position percentage, total exposure, daily simulated loss, portfolio drawdown, daily fill count, sector exposure, minimum cash reserve, order value, and stale prices. Rejections state the exact failed rule. Filled sells cannot exceed the owned quantity.
