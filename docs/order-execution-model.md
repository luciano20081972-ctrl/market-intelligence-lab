# Simulated order execution model

The order engine reads the latest eligible stored daily bar. It applies a $1 default commission, 2 bps spread, and 1 bp slippage. These defaults are recorded with the order/fill. Money and quantities use decimal arithmetic.

- A market order uses the stored open, then applies adverse friction.
- A buy limit fills at the open when the open is at or below its limit; otherwise it fills at the limit when the low touches it. A sell limit uses the symmetric open/high rule. Applied friction is clamped so a limit is never violated.
- A buy stop triggers when the high reaches its threshold; a sell stop triggers when the low reaches it. A gap uses the adverse open; an intrabar trigger uses the stop threshold before friction.
- A stop-limit order records its triggered state once the stop is reached. If the limit is not marketable it remains triggered and pending, and can still be cancelled. A later eligible bar can satisfy its limit.

Buys that fail cash/risk controls are recorded as rejected with precise reasons. Sells cannot exceed the owned position. `(portfolio_id, client_order_id)` is unique, so retries return the original simulated order and cannot create a second fill.

This model does not represent a real order book, queue priority, partial fills, exchange halts, intraday path ordering, liquidity, latency, or market impact. No order leaves the local database.
