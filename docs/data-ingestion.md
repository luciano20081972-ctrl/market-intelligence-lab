# Data ingestion

## Lifecycle

Jobs are created in queued state for full or incremental mode. Execution records the provider, request configuration, attempts, timestamps, processing duration, counts, a resume cursor, validation reports, batches, and structured errors. Successful batches advance the cursor; interrupted, retrying, failed, or cancelled jobs can be restarted without repeating completed symbols.

Temporary provider failures enter retrying with capped exponential backoff. Non-retryable validation failures enter failed. A cancellation request is checked between batches. Per-bar checksums plus the asset/interval/event/source uniqueness constraint prevent duplicate insertion.

## Provenance

Every normalized bar includes provider, original symbol, event/publication/effective/retrieval timestamps, adjustment status, checksum, and record version. Import batches also store a checksum over their ordered record checksums.

## Scheduler boundary

The legacy in-memory scheduler remains only as a compatibility boundary. Version 0.4 uses persisted schedules, jobs, events, leases, and the explicit database-backed worker; it still requires no external broker.
# Version 0.4 durable ingestion

New API imports are queued by default. Idempotency keys suppress duplicate requests. Incremental jobs start after the latest stored provider-source bar; full jobs re-read the requested window. Each successful symbol batch advances a persisted cursor. Workers hold renewable leases, classify retryable provider failures, apply exponential backoff, recover abandoned attempts, and dead-letter exhausted work.

Stooq values are never imputed. Provider/calendar disagreement, malformed values, and conflicting checksums become explicit validation/import issues. Identical rows are skipped; conflicting canonical rows are preserved. Dry-run imports validate and count rows without writing bars. See `worker-operations.md` and `job-state-machine.md`.

## v0.4.1 external preflight

The browser requires a successful preview for the exact external-provider payload before enabling queue submission. Provider, symbols, mode, dates, interval, adjustment preference, and dry-run state are part of that boundary; changing any field invalidates the prior preview. Synthetic demonstration jobs remain queueable offline. Server-side ingestion still revalidates every response, so UI preflight is a usability guard rather than a trust boundary.

Stooq-shaped deterministic fixtures exercise the normal `ImportJob`/`ImportBatch` path, provider symbol mapping, source records, row and batch checksums, non-demonstration classification, duplicate skipping, reconciliation, and imported-mode backtesting. A fixture passing these checks is not evidence that live Stooq connectivity is currently available.

## v0.5 Twelve Data and ownership

Twelve Data uses `Authorization: apikey …` to the allowlisted API host. Daily requests use explicit start/end dates and `adjust=all`, validate JSON/OHLCV/session bounds, cap bodies, normalize errors, and preserve provider symbols, checksum, retrieval time, and the fact that provider publication time is unavailable. User-submitted jobs and schedules carry workspace IDs; scheduled jobs copy the schedule scope. Keys never enter job configuration or metadata.
