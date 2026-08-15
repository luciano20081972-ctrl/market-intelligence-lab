# Provider automation

Initial readiness is deliberately narrow:

| Tier | Source | Readiness |
|---|---|---|
| 1 | SEC | LIVE_OPTIONAL |
| 1 | FRED / ALFRED | LIVE_OPTIONAL |
| 1 | EIA | LIVE_OPTIONAL |
| 1 | configured OHLCV adapters | LIVE_OPTIONAL |
| 2 | other adapters | FIXTURE_ONLY or DISABLED |

No source is labeled PRIVATE_BETA_READY without deployment-specific live evidence. CI uses
fixtures. Live smoke tests require explicit flags, make bounded requests, and never mutate
production. Provider limits, concurrency, user-agent rules, daily budgets, Retry-After, and circuit
breaker state are coordinated through persisted policy/state rather than independent hammering.
