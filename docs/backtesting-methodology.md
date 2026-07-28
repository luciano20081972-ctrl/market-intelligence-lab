# Backtesting methodology

Backtests align daily bars by UTC event time and use a single cash balance across every selected asset. A strategy observes history only through the current bar. Its signal time is the later of that bar's publication and effective time, and execution cannot occur until a later aligned bar after the configured delay. This prevents same-bar and publication-time look-ahead.

Sells execute before buys in deterministic symbol order. The simulator is long-only, permits decimal fractional shares, rejects unaffordable purchases, and prices eligible trades at the next bar open adjusted by half-spread plus slippage and a fixed commission. Target weights use a 1% safety buffer below configured position and total-exposure limits; an observed close beyond the buffered target schedules a next-open rebalance. Price gaps can still temporarily cross a percentage limit.

Every run preserves the immutable strategy version, validated parameters, date/source range, exact price-bar and data-source identifiers, risk settings, execution assumptions, application version, trades, fees, cash, positions, daily equity, benchmark value, exposure, and drawdown. Metrics are derived only from the stored run snapshots and trades.

Limitations include synthetic fixed daily data, no exchange calendar, dividends, splits, corporate actions, intraday liquidity, partial fills, borrowing, taxes, latency distribution, or price impact. Results are hypothetical and do not predict future performance.
