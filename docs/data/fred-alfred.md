# FRED and ALFRED

FRED metadata and observations are acquired directly from the Federal Reserve Bank of St. Louis JSON API. Series identity, title, units, frequency, seasonal adjustment, release/source metadata, notes, and retrieval time are normalized. Missing `.` values become null plus a `missing` quality flag. The standard FRED view is explicitly labelled **latest revised** and must not be used as a historical point-in-time claim.

ALFRED uses the same official API with vintage/realtime parameters. Each observation stores its observation date, `realtime_start` revision, optional `realtime_end`, retrieval time, value, and conservative simulation eligibility. `/macro/series/{id}/as-of` filters eligibility first and returns the newest visible vintage for each period. Tests demonstrate that a later revision cannot appear before its release/retrieval cutoff.

Both adapters support incremental cursors and checksum-idempotent manifests. `MIL_FRED_API_KEY` is backend-only; live tests require `MIL_RUN_LIVE_WORLD_DATA_TESTS=true`. Licensing differs by series, so the registry records `FRED-SERIES-SPECIFIC` rather than asserting redistribution rights.
