# Roadmap

## Sprint 1 — v0.1.0 foundation

Database, migrations, synthetic provenance-complete prices, asset/watchlist API, responsive research UI, tests, CI, Docker, and security documentation.

## Sprint 2 — v0.2.0 backtesting and paper trading

Seven transparent strategies, technical indicators, point-in-time shared-cash backtests, execution friction, metrics and provenance, simulated paper portfolios, deterministic order types, explicit risk controls, and complete API/UI workflows.

## Next recommended sprint — v0.3.0 read-only market ingestion

Implement one well-documented, read-only historical market-data adapter behind the existing provider interface. Add market calendars, corporate-action metadata, retry/rate-limit handling, ingestion-run diagnostics, raw-response checksums, correction/upsert policy, and integration tests recorded from non-secret fixtures. Show an explicit delayed/live/fixed freshness classification throughout the UI. Retain the synthetic provider for offline tests.

This sprint should not add brokerage connectivity or trading.

## Later increments

- SEC filings and filing-section search with accession-number provenance.
- Macroeconomic series with release/vintage semantics.
- Congressional transaction and political/regulatory event timelines.
- Authentication, PostgreSQL deployment, observability, dependency scanning, and backups.

## Sprint 3 — v0.3.0 historical market-data platform

- Provider capability registry and disabled vendor placeholders.
- Durable full and incremental imports with retry, restart, cancellation, provenance, and quality reports.
- Corporate-action models, XNYS exchange sessions, APIs, and governance UI.

## Recommended Sprint 4

- Implement one licensed provider adapter with sandbox credentials and contract tests.
- Replace the finite holiday table with a maintained calendar feed.
- Add a durable worker and scheduler lease model, observability, authentication, rate limiting, and provider license controls.
# After v0.4.0

Sprint 4 completes the first operational historical provider, maintained XNYS calendar, durable single-process queue/worker, daily schedules, health/observability, reconciliation, and imported-data backtests.

Recommended Sprint 5 priorities are complete authentication and authorization, multi-user isolation, distributed rate limiting/worker coordination, provider-terms governance and retention controls, a second independently sourced provider for reconciliation, schedule policies tied to exchange close, and production PostgreSQL concurrency/deployment validation. Brokerage connectivity and real-money execution remain out of scope.
