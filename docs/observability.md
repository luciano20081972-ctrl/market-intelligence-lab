# Operational observability

HTTP responses include `X-Correlation-ID` and `X-Request-Duration-Ms`. Callers may provide a bounded correlation ID. Worker logs include worker, job, provider, status, processed/accepted/rejected counts, retries, and duration. Human-readable logging is the default; `--json-logs` or `MIL_JSON_LOGS=true` emits JSON.

Per-attempt `OperationalMetric` rows record import duration, fetched, accepted, rejected, and retry counts. Queue depth, failed count, worker heartbeat, current job, last successful import, provider configuration/connectivity snapshots, freshness, and quota/rate-limit state are exposed through operations/provider status APIs.

Log rendering redacts authorization, API-key, token, password, and secret-shaped values. Authorization headers, environment contents, database passwords, credentials, and full secret records must never be passed as log fields. Correlation IDs and job identifiers are operational metadata, not authentication.
