# Data ingestion

## Lifecycle

Jobs are created in queued state for full or incremental mode. Execution records the provider, request configuration, attempts, timestamps, processing duration, counts, a resume cursor, validation reports, batches, and structured errors. Successful batches advance the cursor; interrupted, retrying, failed, or cancelled jobs can be restarted without repeating completed symbols.

Temporary provider failures enter retrying with capped exponential backoff. Non-retryable validation failures enter failed. A cancellation request is checked between batches. Per-bar checksums plus the asset/interval/event/source uniqueness constraint prevent duplicate insertion.

## Provenance

Every normalized bar includes provider, original symbol, event/publication/effective/retrieval timestamps, adjustment status, checksum, and record version. Import batches also store a checksum over their ordered record checksums.

## Scheduler boundary

InMemoryImportScheduler exposes daily, manual, retry, and failed queues. It intentionally performs no background work and requires no external services in v0.3.0.
