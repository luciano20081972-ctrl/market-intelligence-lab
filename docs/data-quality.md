# Data quality

The validator reports duplicate bars, missing or naive timestamps, internally impossible OHLC values, nonpositive prices, negative volume, invalid symbols, closed or missing sessions, and stale retrieval timestamps. Reports include checked and valid counts, issue details, severity, record identifiers, and counts by code.

Errors block insertion; freshness warnings do not. Import batches and jobs retain reports for API inspection and the Data Quality dashboard. Database check and unique constraints remain the final integrity boundary.
# Version 0.4 reconciliation

Operational reconciliation adds expected-session gaps, closed-session bars, provider/canonical duplicates, invalid OHLC, negative/zero volume, stale latest data, unexpected gaps, symbol mismatch, adjustment inconsistency, checksum changes, and conflicting reimports. Preview mode writes nothing. Recorded mode stores findings and a preserved/manual-review decision but never overwrites a canonical bar.

Stooq lacks authoritative adjustment and publication metadata in the selected CSV interface. Rows are labeled `provider_unspecified`, retrieval time is used as publication time, and adjusted-only workflows reject them. These limitations are part of provenance rather than hidden transformations.
