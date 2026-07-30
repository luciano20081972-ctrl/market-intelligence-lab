# Architecture

## Shape

The repository is a modular monorepo with an API process, an explicit optional worker process, and one browser application. FastAPI owns transport concerns; reusable packages own data and domain behavior. React talks only to the versioned JSON API through a typed client.

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
5. **Provider isolation.** Capability protocols and a registry prevent provider-specific payloads from entering API or persistence layers. Disabled placeholders make configuration state explicit and safe.
6. **No brokerage execution capability.** Backtests and paper orders are database-only simulations. They cannot authenticate with or submit to a broker.
7. **Conservative interface.** Dark neutral surfaces and restrained status colors emphasize data density without implying predictive certainty.
8. **Versioned reproducibility.** A backtest references an immutable strategy version and stores parameters, execution assumptions, risk limits, application version, and source identifiers.
9. **Point-in-time eligibility.** A signal cannot execute before a later bar after its effective/publication time and configured delay. Assets compete for shared cash in deterministic symbol order.

## Runtime lifecycle

`scripts/dev.py` validates settings and prerequisites, creates required local directories, applies migrations, optionally seeds, then supervises Uvicorn and Vite. A failure or Ctrl+C terminates both children. Containers apply the same migrations and seed through `scripts/container_start.py`.

## Extension points

Production adapters should implement the capability protocols, map raw observations into provenance-complete records, and write them through the ingestion service. Research strategies should consume normalized read models, not provider payloads or API schemas.

## Market-data ingestion flow

ProviderRegistry -> adapter records -> quality validation -> ImportBatch -> normalized models

Each import job is durable and resumes at a symbol cursor. Per-record and per-batch checksums prevent duplicates, while database uniqueness constraints provide a concurrent-write backstop. Exchange sessions are seeded independently and validation rejects bars on closed sessions. Raw close values remain immutable; adjusted values and the adjustment status are stored alongside them.

The current in-memory scheduler is only an orchestration boundary. A later worker can claim the same daily, manual, retry, and failed queues without changing the job model or API.
# Version 0.4 operational topology

The API only validates and persists import requests. An explicit `packages.market_data.worker` process owns execution; it polls the same database, creates schedules, recovers expired leases, conditionally claims one job, renews ownership, and writes bars/events/metrics in transactions. No worker thread starts during API import or tests.

Stooq retains its fixed HTTPS CSV endpoint and honest degraded classification. Twelve Data adds a documented, credentialed, fixed-host JSON adapter that remains disabled when unconfigured and fixture-tested rather than live-verified. `exchange-calendars` supplies maintained XNYS schedules.

# Version 0.5 security topology

The browser's supported Supabase client restores/refreshes sessions and sends a Bearer token. FastAPI verifies asymmetric JWKS claims, resolves an internal user profile and membership, then applies centralized role and workspace policy. Canonical market data stays shared; user research, simulations, schedules, comparisons, and audit views are tenant-scoped. Vendor objects never become canonical domain models. RLS is deliberately not claimed; see the workspace-isolation guide.
