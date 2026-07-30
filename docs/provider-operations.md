# Provider operations

`GET /api/v1/providers` and `GET /api/v1/providers/{id}` expose non-secret configuration. `GET /status` separates configured state, stored health, connectivity test status, last successful import, staleness, authentication requirements, and rate-limit state. `POST /test` performs an explicit connectivity request and persists a `ProviderHealthSnapshot`; merely importing the API never contacts a provider.

Stooq is enabled without credentials. Synthetic remains enabled only for deterministic demonstration and test workflows. Alpha Vantage, Twelve Data, Polygon, Financial Modeling Prep, Tiingo, and Yahoo Finance remain disabled placeholders. Environment variable names may be stored, but secret values must remain environment-only and must not be logged or persisted.

Failures are classified as retryable timeout/network/HTTP 429/5xx or permanent request/response validation errors. A missing optional provider credential must yield `unconfigured` for that provider, not make API liveness or database readiness unavailable.

## v0.4.1 health semantics

- `healthy` / `connected` means a bounded probe returned compatible CSV containing validated OHLCV rows.
- `degraded` / `reachable_invalid` means the HTTPS endpoint responded but returned HTML, an access/rate response, an unexpected content type, a schema mismatch, or malformed market data.
- `degraded` / `reachable_no_data` means the endpoint responded with a recognized no-data result; the schema boundary is considered compatible but no observation is available.
- `unavailable` means the endpoint could not be reached. A pre-request validation error never establishes reachability.

Snapshots include reachable, valid-response, schema-compatible, data-available, degraded/unavailable flags, an allowlisted response classification, a static safe diagnostic message, and timestamp. They never include the response body, cookies, headers, credentials, or environment values. The provider-detail UI displays the same safe classification. An external import can be queued only after the exact current request passes preview validation; changing any request field invalidates that approval.

Twelve Data starts `unconfigured`, becomes `unknown/not_tested` only when its environment key exists, and may become healthy only after a valid live response imports bars. Fixture success is displayed separately. Stooq is never promoted based on fixtures. Provider management requires workspace provider permission; definitions remain system-shared.
