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
