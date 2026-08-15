# Architecture

v0.13 closes the bounded research loop: frozen forecast → mature outcome → type-specific score → calibration/attribution → versioned reliability → human-reviewed feedback. A separate deterministic boundary maps eligible research to a paper allocation candidate and immutable paper plan; existing simulated execution and risk controls remain authoritative.

## v0.12 adversarial, scenario, and counterfactual intelligence

An immutable Research Case bounds references to the v0.8 graph, v0.9 Feature Snapshot, v0.10 hypothesis/experiment, and v0.11 memory/independence/divergence state. Deterministic Skeptic Review precedes bounded Scenario and isolated Counterfactual runs; their manifests feed transparent confidence, fragility, and dossier outputs. No component is a trading agent or causal oracle.

## v0.10 hypothesis factory and factor validation

The v0.9 `ResearchCandidate` and immutable `FeatureSnapshot` feed a bounded Hypothesis Factory. A hypothesis records a proposed mechanism and evidence rather than causal proof; a declarative `CandidateFeatureSpec` is bound to a measurable outcome and immutable `FactorExperiment`. Explicit train, validation, and sealed final-test boundaries flow into retained walk-forward folds, corrected statistics, robustness variants, controls, and sequential promotion events. PostgreSQL remains authoritative for Temporal Truth, universes, graph state, lineage, budgets, and audit history. Qlib and RD-Agent are optional adapters behind internal interfaces and cannot bypass MIL validation.

## v0.9 progressive research and feature store

The Economic Driver Graph is a workspace-scoped relational adjacency model in PostgreSQL. Canonical entities connect through typed, evidence-backed, temporally valid relationships. A bounded recursive query supplies explainable paths to versioned Company Driver Profiles; the deterministic Data Relevance Router then decides which datasets to process, defer, ignore, or review. v0.9 adds versioned universes, immutable point-in-time feature values, grouped lineage, progressive resolution, budgets, screening decisions, and reproducible snapshots. PostgreSQL remains the beta system of record; dense immutable historical matrices can move to Parquet without moving metadata or candidate state.

## Post-v0.6 direction: entity-specific world intelligence

The v0.6 platform remains the operational foundation, but the research product is now defined as discovery and validation of company-specific economic drivers—not a fixed-factor stock predictor. The target flow is:

```text
high-density sources -> Temporal Truth -> entity/exposure graph -> relevance routing
-> point-in-time feature store -> progressive resolution -> screening/promotion
-> hypotheses -> quantitative validation -> research memory
-> divergence and scenarios
```

AI works on bounded, cited evidence packets selected from durable structured data. It does not repeatedly crawl the web, own canonical calculations, approve signals, or modify production source code. PostgreSQL remains the transactional system of record; object storage/Parquet is proposed for large immutable payloads; optional upstream engines remain behind process or package adapters.

The controlling design is [world-intelligence.md](architecture/world-intelligence.md). Detailed decisions cover [Temporal Truth](architecture/temporal-truth.md), the [economic driver graph](architecture/economic-driver-graph.md), [relevance routing](architecture/data-relevance-router.md), [progressive resolution](architecture/progressive-resolution.md), the [hypothesis factory](architecture/hypothesis-factory.md), [research memory](architecture/research-memory.md), [divergence](architecture/divergence-engine.md), [signal independence](architecture/signal-independence.md), [scenarios](architecture/scenario-engine.md), [runtime AI](architecture/runtime-ai.md), and [information value](architecture/information-value.md).

Version 0.9 implements the scalability layer through screening and promotion. Hypothesis generation, predictive validation, Research Memory, divergence, scenarios, and autonomous research agents remain future work.

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
10. **Seven-clock world data.** Event, observation, publication, retrieval, effective, revision, and simulation-eligible time remain distinct; as-of reads filter on eligibility before selecting the newest visible revision.
11. **Immutable raw acquisition.** Content-addressed logical keys and manifests preserve the exact acquired bytes. Normalized rows reference a manifest; raw provider payloads never become API contracts.

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
# v0.11 research-intelligence layer

Research Memory now consumes finalized Factor Validation artifacts and supplies pre-scheduling classification to research workflows. Contradiction and regime records contextualize those lessons. Signal Independence compares candidates with a versioned conventional baseline, while the Divergence Engine turns declarative cross-domain disagreement into evidence-backed research candidates. Information Value, method reliability, and outcome attribution describe research efficiency.

All new records are workspace scoped. Memory and divergence use explicit simulation-eligible timestamps. The layer does not submit orders, infer causality, or implement the future Skeptic, Scenario, Counterfactual, portfolio-allocation, or autonomous self-modification systems.
