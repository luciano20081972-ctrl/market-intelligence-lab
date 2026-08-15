# Testing

## v0.10 factor-research verification

`tests/test_hypothesis_factory.py` covers lifecycle rejection, declarative DSL safety, non-overlapping sealed partitions, walk-forward and purge/embargo behavior, factor/quantile statistics, three multiple-testing corrections, incrementality, robustness, ablation, controls, all nine leakage attacks, sequential promotion, budgets/manifests, optional-engine absence, differentiated archetypes, and the intentionally rejected agriculture hypothesis. PostgreSQL-marked tests add schema constraints/indexes, exclusive experiment claiming, and completed-experiment immutability. Migration tests apply an empty schema, preserve v0.9 data through `2f9e39afd435 → ed23735efb90`, repeat the upgrade, and run Alembic drift detection.

Run `python scripts/benchmark_hypothesis_research.py` for the bounded 100-hypothesis, 1,000-experiment, 10,000-fold workload and 10/50/100-company resource estimates. Runtime AI, Qlib, RD-Agent, and upstream network access are not required by ordinary tests.

## v0.9 feature-store verification

Coverage adds feature definition/version/immutability/lineage; universe and membership history; simulation-eligible as-of retrieval; future feature, universe, graph, SEC, ALFRED, normalization, and screening leakage boundaries; feature quality; safe normalization; materialization idempotency/claims/router skipping; budget enforcement; deterministic promotion/demotion; snapshot and screening reproducibility; workspace API isolation; full research-funnel frontend/Playwright workflows; and a bounded feature-store benchmark. Run `python scripts/benchmark_feature_store.py`; add `--postgres-url-env MIL_POSTGRES_TEST_DATABASE_URL` only for a disposable PostgreSQL 17 database.

## v0.8 graph verification

Backend coverage includes identity normalization/ambiguity/manual decisions, database uniqueness, evidence gates and conflict preservation, confidence components, expiry, strong as-of leakage boundaries, cycle/depth/node limits, priors, routing, overrides, durable recomputation, workspace isolation, deterministic SEC extraction, series linking, graph quality, APIs, and idempotent three-company fixtures. PostgreSQL-marked coverage adds native constraints, timezone round-trips, recursive CTE/as-of behavior, expected indexes, rollback, and concurrent job claims.

Frontend unit and Playwright workflows cover the bounded graph explorer, differentiated company profiles, relationship evidence, routing decisions, and resolution review without severe console errors. Run the requested beta benchmark with `python scripts/benchmark_economic_graph.py --sizes 10000:50000`; use `--sizes 100000:500000` when resources allow, and add `--postgres-url-env MIL_POSTGRES_TEST_DATABASE_URL` for an isolated PostgreSQL EXPLAIN ANALYZE report.

## Backend

Pytest uses an isolated SQLite database per test. Coverage includes the foundation workflows plus indicator calculations, seven strategy contracts, strict parameter validation, shared-cash and delayed no-lookahead backtests, costs and exposure controls, metrics and provenance, paper market/limit/stop/stop-limit behavior, idempotency, long-only enforcement, fills, P&L, pause/resume, risk rejections, provider registration, durable imports, retries/restarts, provenance, quality validation, corporate actions, exchange calendars, and API validation.

Run `pytest`, `ruff check .`, and `mypy apps packages scripts` from the root. CI also applies Alembic to an empty database and runs `alembic check`.

v0.6 additionally runs `python scripts/validate_upstream.py`. Deterministic fixtures cover SEC
forms/facts/insiders/13F, analytics reconciliation, constrained optimization, and LEAN result
packages without network or brokerage access. Live SEC verification requires
`MIL_RUN_LIVE_SEC_TESTS=true` and an explicitly configured bounded worker; it is skipped by
default. PostgreSQL 17 CI remains the destructive migration/concurrency environment.

## Frontend

Vitest and React Testing Library cover the foundation screens, backtesting and paper-trading workflows, provider health, import creation/detail, data quality, corporate actions, and exchange sessions. Run `pnpm test`, `pnpm run typecheck`, and `pnpm run build` from `apps/web`.

## Browser workflow

The Playwright smoke test loads the application, finds a seeded asset, creates a watchlist, adds AAPL, opens its detail page, and fails on browser-console errors. Install Chromium once with `pnpm exec playwright install chromium`, then run `pnpm run test:e2e`.

Tests must not be reported as passed unless they ran. Docker verification is distinct from source-level verification and is reported separately when Docker is unavailable.
# Sprint 4 verification

Provider unit tests use `httpx.MockTransport` and deterministic CSV fixtures; ordinary tests never access the internet. Queue tests cover idempotency, claim exclusivity, lease renewal/expiry, abandoned recovery, metrics, scheduling deduplication, cancellation, restart cursors, and graceful shutdown. Calendar coverage validates a post-2027 holiday and early close. Reconciliation and imported/mixed backtest tests verify non-destructive outcomes and provenance.

Run `python scripts/verify.py` for backend tests/Ruff/MyPy and frontend TypeScript/Vitest/build. Run Playwright separately after installing Chromium. An optional one-request Stooq smoke test is documented in `real-market-data.md` and is never part of the default suite.

## v0.4.1 provider stabilization

Sanitized fixtures cover canonical CSV, safe header normalization, UTF-8 BOM, empty/no-data, HTML verification, unsupported symbol, malformed/duplicate schema, invalid dates/numbers/OHLC, and negative/fractional volume. Mock-transport tests cover the fixed HTTPS endpoint/query, `.us` mapping for AAPL/MSFT/SPY, redirect/content-type rejection, limits, timeout/rate/server errors, safe diagnostics, and health-state persistence. A deterministic Stooq-shaped integration imports 60 AAPL/SPY bars through durable jobs, verifies idempotent reimport and provenance, runs reconciliation, and completes an imported-data backtest.

Frontend tests cover healthy, reachable-invalid, unavailable, schema-mismatch, and no-data diagnostics plus exact-request import prevention. Playwright deterministically stubs only the provider connection response, displays its classification, then continues through the offline synthetic import/provenance/imported-backtest workflow without severe console errors. The Stooq-shaped fixture path is verified in backend integration tests. Default automated tests never contact Stooq, and live status is reported separately from fixture results.

## v0.5 verification

Backend tests cover JWT claim/signature failures, production config refusal, disabled users, workspace list/ID isolation, viewer denial, audits, Twelve Data fixtures/errors, provider conflict recording, manifests, critical validation, and safe infrastructure metadata. `pytest -m postgres` is skipped unless a disposable PostgreSQL URL is explicit; CI supplies one. Frontend tests cover login/error/expiry, permission-aware membership actions, audits, comparisons, manifests, validation, and infrastructure.

Coverage emits XML and LCOV; local thresholds are authoritative and Codecov upload is optional. Supply-chain CI runs lock verification, `pip-audit`, high-level npm audit, CycloneDX generation, and Python/npm license reports. Live Supabase/provider calls remain opt-in and are never ordinary-test dependencies.

For v0.5.1, `scripts/validate_supabase_staging.py` is the bounded live Auth
rehearsal. It requires the ignored staging file, exact project reference, HTTPS,
both backend/public keys, and `MIL_RUN_LIVE_SUPABASE_TESTS=true`; it reports
booleans only and deletes temporary users in a `finally` cleanup path. Ordinary
tests never load this configuration. Supply-chain CI rejects high and critical
npm advisories.
# v0.7 temporal validation

The world-data suite covers UTC normalization, naive-time rejection, publication/retrieval/revision eligibility floors, future-vintage exclusion, immutable manifests and raw objects, registry completeness, SEC identifier/amendment normalization, missing FRED values, ALFRED leakage prevention, EIA units/geography, idempotency, protected APIs, clean migration, upgrade from v0.6, drift, PostgreSQL 17, and opt-in bounded live probes. Fixture success must never be described as live verification.
# v0.11 verification

The research-intelligence suite covers positive and negative memory, applicability, suppression and override audit, as-of leakage boundaries, deterministic Pearson/Spearman/residual statistics, redundant-versus-independent behavior, divergence without trade eligibility, contradiction/regime/cluster semantics, lifecycle immutability, and workspace scope. Frontend tests cover all new views; Playwright covers the integrated signed-in navigation path. Database gates include clean, incremental, repeated, drift, identifier-length, and rollback checks on disposable PostgreSQL 17 when configured.
