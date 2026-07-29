# Provider operations

`GET /api/v1/providers` and `GET /api/v1/providers/{id}` expose non-secret configuration. `GET /status` separates configured state, stored health, connectivity test status, last successful import, staleness, authentication requirements, and rate-limit state. `POST /test` performs an explicit connectivity request and persists a `ProviderHealthSnapshot`; merely importing the API never contacts a provider.

Stooq is enabled without credentials. Synthetic remains enabled only for deterministic demonstration and test workflows. Alpha Vantage, Twelve Data, Polygon, Financial Modeling Prep, Tiingo, and Yahoo Finance remain disabled placeholders. Environment variable names may be stored, but secret values must remain environment-only and must not be logged or persisted.

Failures are classified as retryable timeout/network/HTTP 429/5xx or permanent request/response validation errors. A missing optional provider credential must yield `unconfigured` for that provider, not make API liveness or database readiness unavailable.
