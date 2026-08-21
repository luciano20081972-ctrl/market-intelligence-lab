# Real Market Foundation v0.15

The canonical security master keeps stable `assets.id` identities while recording time-valid
listings, source identifiers, issuer enrichment, reference observations, provider mappings, and
capabilities. Nasdaq Trader directories supply U.S. listing reference data; SEC ticker/exchange/CIK
data enriches issuer identity and is never treated as a price source.

Massive Basic is the broad end-of-day layer and Alpaca Basic is the active `LIVE — IEX` layer.
Both adapters are fail-closed and disabled until their environment credentials are present.
Provider plan details are runtime entitlements: request rates and Alpaca realtime capacity are
configuration, not business constants. Stooq is `BEST_EFFORT_FALLBACK`; Twelve Data remains an
optional adapter; synthetic bars remain explicitly classified demonstration data.

Four durable PostgreSQL-coordinated tasks maintain the reference catalog, queue historical
backfill, select the layered market universe, and persist calendar-driven operating mode. MARKET
mode budgets one ingestion-heavy and one lightweight intelligence job and records a 1 GiB headroom
target. Jobs retain checkpoints, retries, queue wait, duration, and optional peak-memory fields.

No live provider request runs by default. An operator must provide `MIL_MASSIVE_API_KEY`,
`MIL_ALPACA_API_KEY_ID`, and `MIL_ALPACA_API_SECRET`, confirm plan entitlements, and explicitly
enable the bounded reference network refresh before a production-data rehearsal.
