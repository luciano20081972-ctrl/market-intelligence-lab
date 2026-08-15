# Data freshness

Freshness is CURRENT, DUE, STALE, VERY_STALE, UNKNOWN, or PROVIDER_DELAYED. It uses expected
publication cadence, last eligible publication, last successful ingestion, provider delay, market
calendar, timezone, weekends, and holidays. A Friday daily bar remains current over the weekend.
The UI distinguishes stale data from a source that has not published yet.
