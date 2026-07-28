# Data provenance

Every stored price bar records:

- **Source:** the provider responsible for the observation.
- **Event time:** when the market observation occurred.
- **Publication time:** when the source made it available.
- **Effective time:** when the value should be considered applicable.
- **Retrieval time:** when this system obtained it.
- **Demonstration flag:** whether the value is synthetic rather than sourced market data.

Keeping these times separate prevents look-ahead bias: a backtest must not use a value before its publication/retrieval policy permits it. Future corrected observations can preserve their original event time while recording a later publication and retrieval.

The v0.1.0 provider is deterministic and synthetic. It uses a fixed seed, fixed UTC date range, stable UUID namespace, and stable retrieval schedule. It creates exactly 120 weekday bars for each of SPY, QQQ, AAPL, MSFT, NVDA, AMZN, GOOGL, META, and TSLA. It is not calibrated to real historical prices.

Live adapters must document vendor identity, license terms, adjustment method, exchange calendar, correction policy, rate limits, and retention rights before their data can be enabled.
