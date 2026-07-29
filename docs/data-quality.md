# Data quality

The validator reports duplicate bars, missing or naive timestamps, internally impossible OHLC values, nonpositive prices, negative volume, invalid symbols, closed or missing sessions, and stale retrieval timestamps. Reports include checked and valid counts, issue details, severity, record identifiers, and counts by code.

Errors block insertion; freshness warnings do not. Import batches and jobs retain reports for API inspection and the Data Quality dashboard. Database check and unique constraints remain the final integrity boundary.
