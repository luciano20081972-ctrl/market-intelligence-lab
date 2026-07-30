# Rate limiting

Expensive provider tests, import previews, and abandoned-job recovery use a fixed-window application limiter keyed by client address and path. Configure the per-minute bound with `MIL_EXPENSIVE_REQUEST_LIMIT_PER_MINUTE`; the default is 10. Provider HTTP 429 responses are separately recorded in `ProviderRateLimitState` and drive durable job retry scheduling.

The application limiter is intentionally in-process. Counters reset on restart and are not shared between API replicas, so it is suitable only for the current single-instance deployment. It is defense-in-depth, not authentication or distributed abuse prevention. Authentication and workspace authorization are implemented in v0.5; a Redis-compatible shared limiter remains a pre-private-beta deployment item.

Twelve Data's provider quota is separate: HTTP/provider code 429 becomes a retryable normalized error without returning the raw body. The documented free allowance is governance metadata, not an entitlement guarantee; operators must recheck the current plan and alert before its registry threshold.
