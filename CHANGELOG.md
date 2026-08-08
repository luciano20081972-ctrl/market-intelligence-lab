# Changelog

## 0.6.0 - 2026-07-30

- Added machine-validated upstream license, dependency, notice, and provenance governance for seven evaluated projects and every direct Python/frontend dependency.
- Added internal SEC, analytics, optimization, and external-backtest protocols; no upstream source files were copied.
- Added fixture-first EdgarTools integration for normalized 10-K, 10-Q, 8-K, Forms 3/4/5, 13F-HR, company submissions, company facts/XBRL, provenance, timestamps, checksums, and idempotent imports.
- Added QuantStats-compatible metric reconciliation and structured report metadata, plus a skfolio-compatible deterministic constrained optimization foundation with no shorting or leverage by default.
- Added a disabled-by-default LEAN adapter prototype with installation detection, request validation, reproducibility manifest, normalized fixture result, and internal-versus-LEAN comparison. No live mode, cloud dependency, or brokerage credential path exists.
- Added Alembic revision `6b8d9e0f1a2b`, protected APIs, nine frontend views, deterministic backend/frontend/Playwright coverage, and PostgreSQL/Data API lockdown for the new application tables.
- Classified OpenBB and FinceptTerminal as AGPL/reference-only; NautilusTrader remains an evaluated LGPL optional engine. No restricted code, assets, branding, filings, or generated reports are vendored.

### Limitations

- Live SEC retrieval is explicitly gated and not verified in this release environment.
- Optional third-party libraries may be unavailable; compatibility fixtures remain available.
- LEAN subprocess/container execution and resource enforcement are design contracts only in v0.6.
- Trading remains simulated, with no brokerage or real-money execution and no performance guarantee.

## 0.5.1 - 2026-07-30

- Added Alembic revision `cba31be9f005` to enable deny-by-default RLS on every application table, revoke direct `anon`/`authenticated` table and function privileges, and harden default privileges without changing Supabase-managed schemas.
- Added Alembic revision `4a2523700bdb` to index all four `source_price_bar_id` foreign keys identified by the staging schema audit.
- Added connector-transport deployment documentation that maps every controlled staging SQL batch back to the canonical Alembic chain while the direct session-pooler login remains unresolved.
- Added schema-aware staging/production readiness, separate migration/runtime URLs, explicit psycopg v3 URL normalization, and secret-free Supabase validation settings.
- Live-verified temporary Supabase password identities, asymmetric JWT claims, refresh/sign-out revocation, identity endpoints, Data API denial, workspace authorization, audit redaction, and complete temporary-user cleanup.
- Expanded SQLite upgrade rehearsals and disposable PostgreSQL 17 CI coverage for the v0.5-to-v0.5.1 transition, RLS state, workspace guards, leases, concurrency, UUID, decimal, timezone, rollback, and drift.
- Corrected v0.5 legacy-workspace data-migration bind parameters to compile as UUID rather than VARCHAR on PostgreSQL.
- Remediated frontend dependency advisories by moving to React Router 8.3.0 and the compatible Vitest/coverage 4.1.10 toolchain; the release audit reports no known npm vulnerabilities.
- Updated Supabase staging, authentication, workspace-isolation, database, backup, and security documentation. No brokerage connectivity or real-money execution was added.

## 0.5.0 - 2026-07-30

### Added

- Provider-neutral authentication with Supabase asymmetric-JWKS verification, supported frontend session/reset flows, production refusal of disabled auth, and safe redaction boundaries.
- Deterministic legacy user/workspace migration, memberships/invitations, owner/admin/member/viewer permissions, centralized tenant scoping, negative isolation tests, and enriched immutable audit events.
- Fixture-tested Twelve Data daily OHLCV adapter and ADR, cross-provider tolerance comparison with explicit conflict resolution, and honest Stooq live limitation.
- Per-backtest reproducibility manifests and deterministic bias/leakage reports; critical publication leakage prevents validated status.
- Seven-service infrastructure registry, safe administrative UI/API, security/threat/exit/cost documentation, optional scrubbed Sentry wiring, Codecov-compatible reports, Dependabot, SBOM, license, vulnerability, and PostgreSQL CI jobs.
- Alembic revision `18cca98a50d5` preserving existing records in the deterministic legacy workspace.

### Limitations

- PostgreSQL RLS is not implemented or claimed; application scoping is mandatory and RLS remains pre-v1.0 hardening.
- Twelve Data and Supabase are not live-verified. Optional vendor accounts were not provisioned.
- Trading remains simulated; no brokerage, Fidelity, real-money, options, margin, short selling, withdrawals, or autonomous trading were added.

## 0.4.1 - 2026-07-29

### Fixed

- Classified Stooq response envelopes before CSV parsing, including the observed HTTP 200 `text/html` verification/access response, safe no-data/symbol/access/rate/content-type/network errors, response limits, and redirect rejection.
- Preserved strict canonical OHLCV validation while safely normalizing UTF-8 BOMs, ASCII header capitalization, surrounding header whitespace, and line endings; unobserved semicolon delimiters remain rejected.
- Restricted symbol mapping to confirmed simple U.S. stock and ETF forms (`AAPL`, `MSFT`, and `SPY` map to `.us`) and added a precise invalid-date-range boundary.
- Persisted provider health as healthy, degraded reachable-invalid/reachable-no-data, or unavailable with safe response classifications and messages.
- Required a successful preview of the exact request before the UI can queue an external import.

### Tests and documentation

- Added sanitized provider fixtures and deterministic coverage for response classification, strict parsing, idempotent durable Stooq-shaped imports, provenance, reconciliation, and imported-data backtesting.
- Expanded frontend and Playwright coverage for safe provider diagnostics and documented fixture-tested versus live-verified behavior, provider limitations, and licensing caveats.
- No database migration was required.

### Safety

- Trading remains simulated. No authentication, multi-user, brokerage, credential-storage, real-order, or general Sprint 5 capability was added.
- Unexpected remote bodies are not logged or displayed, and no provider-data redistribution right is claimed.

## 0.4.0 - 2026-07-29

### Added

- Operational, read-only Stooq daily OHLCV adapter with fixed URL allowlisting, symbol mapping, bounded requests, timeouts, response limits, normalized errors, fixture coverage, checksums, and audit metadata.
- Maintained `exchange-calendars` XNYS sessions beyond 2027, including holidays, timezones, and early closes.
- Database-backed single-process import queue with leases, heartbeats, retries, cancellation, abandoned recovery, dead-letter state, cursors, idempotency, and persisted job events.
- Explicit worker command, recurring daily schedules, operational metrics and logs, health/readiness endpoints, provider status snapshots, and application-level expensive-request rate limits.
- Dry-run and persisted reconciliation for gaps, sessions, duplicates, OHLC/volume, stale data, symbols, adjustment state, checksum changes, and preserved conflicts.
- Provider detail, import preview/timeline, queue/worker dashboard, schedule management, reconciliation UI, and imported-data backtest provenance.
- Alembic revision `1a52c2d25013` and clean plus v0.3 upgrade rehearsals.

### Safety

- Trading remains entirely simulated. No broker, Fidelity, live order, autonomous trading, or credential-storage capability was added.
- Provider data is not bundled and no commercial redistribution license is claimed.

## 0.3.0 - 2026-07-28

### Added

- Provider registry and disabled placeholders for seven future market-data vendors.
- Durable full/incremental import jobs with batches, retry/backoff, cancellation, restart cursors, checksums, duplicate prevention, history, and precise errors.
- Provenance-complete price bars, metadata versions, corporate actions, exchange calendars, and trading sessions.
- Data-quality validation and reports for symbols, timestamps, OHLC, volume, duplicates, sessions, and freshness.
- Market-data APIs and six frontend workspaces for providers, imports, quality, actions, and calendars.
- In-memory scheduler abstraction for daily, manual, retry, and failed queues.

### Safety

- All trading remains simulated. Provider placeholders are disabled and perform no external network calls.

All notable changes follow Keep a Changelog conventions. The project uses semantic versioning.

## [0.2.0] - 2026-07-28

### Added

- Seven versioned transparent strategies and deterministic SMA, EMA, RSI, MACD, ATR, return, volatility, volume, relative-strength, and drawdown indicators.
- Shared-cash, long-only, point-in-time backtests with delayed execution, transaction-cost assumptions, benchmark comparison, provenance, risk sizing, trades, signals, and daily snapshots.
- Simulated portfolios with idempotent market, limit, stop, and stop-limit orders; fills, positions, P&L, performance snapshots, pause/resume, and nine configurable pre-trade risk rules.
- Versioned strategy, backtest, paper-portfolio, order, fill, position, performance, and risk-rule APIs.
- Strategy Lab, backtest reports, paper portfolio dashboard, simulated order ticket, and risk settings interface.
- Alembic revision `0002_backtesting_paper_trading`, backend behavioral coverage, and Sprint 2 frontend workflow tests.

### Safety

- All results and orders are explicitly hypothetical. No brokerage connectivity, credentials, margin, options, short selling, force execution, or real-money capability was added.

## [0.1.0] - 2026-07-28

### Added

- FastAPI and SQLAlchemy foundation with versioned system, asset, price, and watchlist APIs.
- Alembic foundation migration and portable SQLite/PostgreSQL-oriented schema.
- Deterministic nine-asset dataset with 1,080 source-labeled daily bars.
- Responsive React research interface with overview, watchlists, asset explorer/detail, sources, status, and documentation.
- Provenance timestamps, ingestion runs, audit events, UTC enforcement, transactional mutations, and database constraints.
- Backend, frontend, and Playwright tests; Ruff, MyPy, Vitest, build, migration, and CI checks.
- Cross-platform development launcher, Docker images, Compose topology, and security/operations documentation.
