# Architecture

## Shape

The repository is a modular monorepo with one Python process and one browser application. FastAPI owns transport concerns; reusable packages own data and domain behavior. React talks only to the versioned JSON API through a typed client.

```text
React/Vite -> /api/v1 -> FastAPI routers -> SQLAlchemy sessions -> SQLite/PostgreSQL
                                      |-> provider contracts -> ingestion/provenance
                                      |-> versioned strategies -> backtest engine
                                      \-> risk rules -> simulated order engine
```

## Decisions

1. **API versioning from day one.** Stable `/api/v1` paths let future clients coexist with breaking changes.
2. **Database constraints are authoritative.** Application validation improves messages; unique, foreign-key, and check constraints protect concurrent writes.
3. **Explicit transaction ownership.** Read dependencies close sessions. Mutation handlers commit intentionally and roll back integrity failures before returning a conflict.
4. **UTC and bitemporal-minded provenance.** Event, publication, effective, and retrieval time are distinct. A custom type rejects naive Python timestamps and restores timezone awareness after SQLite reads.
5. **Provider isolation.** `MarketDataProvider` and `ProviderPriceBar` prevent provider-specific payloads from entering API or persistence layers.
6. **No brokerage execution capability.** Backtests and paper orders are database-only simulations. They cannot authenticate with or submit to a broker.
7. **Conservative interface.** Dark neutral surfaces and restrained status colors emphasize data density without implying predictive certainty.
8. **Versioned reproducibility.** A backtest references an immutable strategy version and stores parameters, execution assumptions, risk limits, application version, and source identifiers.
9. **Point-in-time eligibility.** A signal cannot execute before a later bar after its effective/publication time and configured delay. Assets compete for shared cash in deterministic symbol order.

## Runtime lifecycle

`scripts/dev.py` validates settings and prerequisites, creates required local directories, applies migrations, optionally seeds, then supervises Uvicorn and Vite. A failure or Ctrl+C terminates both children. Containers apply the same migrations and seed through `scripts/container_start.py`.

## Extension points

Future adapters should implement the market-data provider protocol, map raw observations into provenance-complete records, and write them through a dedicated ingestion service. Research strategies should consume normalized read models, not provider payloads or API schemas.
