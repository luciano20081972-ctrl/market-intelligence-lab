# Paper trading

Paper portfolios are isolated hypothetical cash accounts. Creating one records starting cash and an initial snapshot. Simulated fills update cash, positions, average cost, realized P&L, unrealized P&L, fees, exposure, and performance snapshots. Portfolio screens expose positions, open and historical orders, fills, risk status, pause status, and value history.

Pausing a portfolio rejects new submissions while leaving pending orders visible and cancellable. Resuming restores submissions. Market, limit, stop, and stop-limit records use stored synthetic prices only. There is no broker adapter, brokerage credential storage, real-time feed, real-money order, withdrawal, margin, option, or short position.

Always preview an order before submitting it. The preview returns an estimated price/value, fee, source bar, deterministic gap assumptions, trigger status, and every failed risk rule. The browser keeps one stable client order ID for the ticket and disables repeat submission after a result; the database uniqueness constraint is the final duplicate guard.
