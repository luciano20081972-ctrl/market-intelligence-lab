# Roadmap

## Release sequence (updated 2026-07-30)

- **v0.5 — implemented/fixture-verified:** secure multi-user and production foundation. Supabase/Twelve Data live verification and PostgreSQL RLS are deferred; PostgreSQL checks run when the disposable service is available.
- **v0.6 — implemented/fixture-verified:** upstream license governance, normalized SEC entities,
  analytics reconciliation, constrained optimization, and optional LEAN contracts. Live SEC and
  actual LEAN process execution remain explicit future validation.
- **v0.7 — recommended:** bounded cached SEC worker/live rehearsal, XBRL taxonomy expansion,
  production object-store references, actual isolated LEAN container conformance, and
  workspace-aware PostgreSQL RLS policies. No real-money execution.
- **Later intelligence scope:** FRED/ALFRED and government-event ingestion with point-in-time provenance.
- **Later research scope:** advanced validation and reporting beyond the v0.6 analytics and optimization foundation.
- **v0.8 — planned:** explainable signal and model research laboratory.
- **v0.9 — planned:** deployment, alerts, backups, monitoring, and private beta.
- **v1.0 — planned:** security review, data-license review, performance hardening, complete RLS decision, and first complete release.

Estimates are one focused sprint per listed minor release, subject to provider licensing and security review. “Fixture-tested” never means “live-verified.”

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
# After v0.4.1

Sprint 4 completes the first operational historical provider, maintained XNYS calendar, durable single-process queue/worker, daily schedules, health/observability, reconciliation, and imported-data backtests. Version 0.4.1 stabilizes Stooq response classification and strict parsing, persists honest health states, and prevents unvalidated external imports. Fixture-backed behavior is complete; live availability remains environment/provider dependent and Stooq still has no SLA or authoritative adjustment/publication semantics.

Sprint 5 implements authentication/authorization, workspace isolation, provider/infrastructure governance, a fixture-tested second provider, non-destructive quorum comparison, manifests, validation reports, and PostgreSQL CI. Recommended Sprint 6 is SEC, FRED/ALFRED, and government-event intelligence with point-in-time release/vintage semantics. Brokerage connectivity and real-money execution remain out of scope.
