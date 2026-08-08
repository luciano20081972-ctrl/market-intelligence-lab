# Architecture

## Post-v0.6 direction: entity-specific world intelligence

The v0.6 platform remains the operational foundation, but the research product is now defined as discovery and validation of company-specific economic drivers—not a fixed-factor stock predictor. The target flow is:

```text
high-density sources -> Temporal Truth -> entity/exposure graph -> feature store
-> relevance routing -> hypotheses -> quantitative validation -> research memory
-> divergence and scenarios
```

AI works on bounded, cited evidence packets selected from durable structured data. It does not repeatedly crawl the web, own canonical calculations, approve signals, or modify production source code. PostgreSQL remains the transactional system of record; object storage/Parquet is proposed for large immutable payloads; optional upstream engines remain behind process or package adapters.

The controlling design is [world-intelligence.md](architecture/world-intelligence.md). Detailed decisions cover [Temporal Truth](architecture/temporal-truth.md), the [economic driver graph](architecture/economic-driver-graph.md), [relevance routing](architecture/data-relevance-router.md), [progressive resolution](architecture/progressive-resolution.md), the [hypothesis factory](architecture/hypothesis-factory.md), [research memory](architecture/research-memory.md), [divergence](architecture/divergence-engine.md), [signal independence](architecture/signal-independence.md), [scenarios](architecture/scenario-engine.md), [runtime AI](architecture/runtime-ai.md), and [information value](architecture/information-value.md).

This is an approved planning boundary only. No v0.7 production subsystem is implemented by these documents.

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

The browser's supported Supabase client restores/refreshes sessions and sends a Bearer token. FastAPI verifies asymmetric JWKS claims, resolves an internal user profile and membership, then applies centralized role and workspace policy. Canonical market data stays shared; user research, simulations, schedules, comparisons, and audit views are tenant-scoped. Vendor objects never become canonical domain models. PostgreSQL RLS is enabled as deny-by-default defense in depth without browser-facing policies; workspace-aware database policies are not claimed. See the workspace-isolation guide.
# v0.6 upstream adapter boundary

External libraries sit behind `SecFilingsProvider`, `PortfolioAnalyticsEngine`,
`PortfolioOptimizer`, and `ExternalBacktestEngine`. Adapters normalize capability, version,
health, timeout/error, provenance, and fixture behavior. Their objects never become API or
database contracts.

EdgarTools, QuantStats, and skfolio are pinned optional dependencies. LEAN is an optional local
process/container design and remains disabled. OpenBB and Fincept are reference-only; no source
or visual expression was copied. Core research, authentication, and simulation continue when
any optional adapter is unavailable.

The post-v0.6 audit classifies provider, auth, workspace, provenance, reproducibility,
migration, testing, and UI foundations as KEEP/EXTEND. Backtesting and upstream engines are
WRAP boundaries. Compatibility-only QuantStats/skfolio calculations are to be replaced by real
pinned adapters after reconciliation. SQLite, fixture-only readiness claims, in-process
multi-host scheduling assumptions, and a fixed universal factor model are deprecated as
production architecture, while remaining useful in bounded tests where noted.
