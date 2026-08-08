# Database

## v0.9 progressive research schema

Alembic revision `2f9e39afd435` (parent `61293cddc2e2`) adds research universes/versions/memberships, feature definitions/versions/sets/values/lineage, materialization jobs, resolution policies, budgets/usage, immutable snapshots, screening runs/decisions, and candidate state. Composite indexes put equality columns before the simulation-eligibility range for as-of point and matrix reads. Every foreign-key hot path is indexed. UTC-aware clocks, half-open validity intervals, unique version/input identities, quality/status constraints, and workspace foreign keys enforce the core invariants. The beta deliberately does not partition; reassess around 100 million feature-value rows.

## v0.8 graph schema

Alembic revision `61293cddc2e2` (parent `7f4af62df2fe`) adds canonical entities, identifiers, aliases, resolution candidates/decisions, relationships, evidence links, confidence components, company profiles/entries, relevance decisions, quality issues, and recomputation jobs. Tables use workspace foreign keys, bounded confidence/status constraints, unique identity mappings, half-open validity intervals, and composite inbound/outbound/as-of indexes. PostgreSQL recursive CTEs serve production traversal; SQLite uses bounded breadth-first traversal for local deterministic tests.

## Models

- `Asset`: normalized symbol and descriptive stock/ETF metadata.
- `PriceBar`: OHLCV observation plus source and four time semantics.
- `DataSource`: provider identity, health, licensing notes, and last success.
- `DataIngestionRun`: status, timing, record count, and safe error summary for a provider run.
- `Watchlist`: named user-curated collection.
- `WatchlistAsset`: many-to-many link with an added timestamp.
- `AuditEvent`: append-only application mutation record.
- `Strategy` / `StrategyVersion`: named strategy identity and immutable validated parameter versions.
- `BacktestRun`, `BacktestTrade`, `BacktestDailySnapshot`: reproducible simulation inputs, executions, metrics, and daily state.
- `Signal` / `SignalFactor`: explainable signal direction, timing, source bar, and indicator factors.
- `PaperPortfolio`, `PaperPosition`, `PaperOrder`, `PaperFill`, `PortfolioSnapshot`: simulated cash, holdings, order lifecycle, execution, and performance history.
- `RiskRule`: enabled portfolio-level pre-trade limits and configuration.

UUID primary keys avoid coupling identifiers to database insertion order and support future distributed ingestion. Symbols and watchlist names are unique. A price bar is unique across asset, interval, event time, and data source.

## Cascades and restrictions

Deleting an asset removes its price bars and watchlist links. Deleting a watchlist removes only its links. Deleting a referenced data source is restricted so provenance cannot silently disappear. SQLite foreign keys are explicitly enabled on every connection.

## Numeric and time behavior

Prices use `NUMERIC(18, 6)` and are serialized as decimals. Volume is a nonnegative integer. All timestamps are aware UTC in application code. SQLite stores timestamps without full timezone semantics, so `UTCDateTime` normalizes writes and restores UTC awareness on reads. PostgreSQL can preserve `TIMESTAMP WITH TIME ZONE` behavior natively.

## Migrations

Revisions `0001_foundation` and `0002_backtesting_paper_trading` are authoritative. Never edit a migration that has shipped; add a new revision. Verify from an empty database with `alembic upgrade head`, then use `alembic check` to detect ORM/schema drift.
# Version 0.4 schema additions

Alembic revision `1a52c2d25013` additively introduces `worker_instances`, `job_leases`, `job_events`, `import_schedules`, `schedule_runs`, `provider_rate_limit_states`, `provider_symbol_mappings`, `reconciliation_runs`, `reconciliation_issues`, `operational_metrics`, and `provider_health_snapshots`.

`import_jobs` gains a unique idempotency key, dry-run and adjustment preferences, and queue name. `price_bars` gains an optional import-job foreign key and non-secret provider metadata. `backtest_runs` records data classification, provider/import identifiers, adjustment states, and calendar code. Existing v0.3 rows receive safe server defaults; price provenance and restrictive foreign keys are preserved. Clean and populated-v0.3 upgrade rehearsals plus `alembic check` are automated.

## v0.5 ownership migration

Revision `18cca98a50d5` adds users, workspaces, memberships, invitations, provider comparisons, backtest manifests, and validation reports. It creates deterministic legacy user/workspace IDs, assigns all existing watchlists, strategies, backtests, paper portfolios, import jobs, and schedules, then makes workspace foreign keys non-null and changes names/idempotency uniqueness to include workspace. Canonical assets/bars/providers/calendars remain shared. Existing audit events are attributed to the legacy context and enriched columns remain append-only through the API.

PostgreSQL is the production database. CI uses PostgreSQL 17 for clean migration, drift, UUID/decimal/timezone, rollback, uniqueness, claim concurrency, and session-context checks. SQLite remains the lightweight local/test path.

## v0.5.1 Data API lockdown

Revision `cba31be9f005` is PostgreSQL-only and additive. It enables RLS on all 47 application tables, revokes application-table/sequence/function privileges from Supabase `anon` and `authenticated` roles when those roles exist, revokes unsafe public function execution, and configures restrictive default privileges for future objects created by the migration owner. SQLite is intentionally unchanged.

There are no RLS policies in v0.5.1. Non-owner roles therefore receive deny-by-default behavior; the PostgreSQL table owner used by FastAPI/Alembic retains owner access and is not subject to these policies. This is PostgREST exposure lockdown, not workspace-aware database authorization. Privilege revocations are not guessed back into existence by downgrade because the previous grants are deployment-specific.

Revision `4a2523700bdb` adds indexes for the `source_price_bar_id` foreign keys on backtest trades, paper fills, paper orders, and signals. The staging foreign-key audit therefore has no unindexed application foreign keys.

## v0.6 upstream and SEC schema

Revision `6b8d9e0f1a2b` adds 11 application tables. `sec_companies`, `sec_filings`,
`sec_documents`, `sec_facts`, `sec_insider_transactions`, and
`sec_institutional_holdings` are shared canonical public-source data.
`sec_ingestion_jobs`, `analytics_comparison_records`, `optimization_experiments`,
and `external_engine_runs` are workspace-owned; parse results connect a workspace
job to shared filings.

Accession numbers are globally unique, SEC dates are distinct from UTC acceptance/retrieval
timestamps, numeric facts/holdings retain fixed precision, and input/result checksums preserve
reproducibility. All new PostgreSQL tables receive the same deny-by-default RLS flag and
conditional Supabase `anon`/`authenticated` revocations as the v0.5.1 application schema.
No Supabase-managed schema is modified.
# v0.7 temporal world-data schema

Alembic revision `7f4af62df2fe` extends `6b8d9e0f1a2b` without rewriting history. `data_manifests`, `raw_data_objects`, and `ingestion_checkpoints` provide immutable provenance and resumability. `macro_series`/`macro_observations` and `energy_series`/`energy_observations` avoid a generic EAV table while sharing the same seven temporal columns, manifest foreign key, quality flags, source timezone, and precision. Composite indexes support series range and point-in-time eligibility queries.
