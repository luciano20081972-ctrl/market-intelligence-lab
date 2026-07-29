# Rate limiting

Expensive provider tests, import previews, and abandoned-job recovery use a fixed-window application limiter keyed by client address and path. Configure the per-minute bound with `MIL_EXPENSIVE_REQUEST_LIMIT_PER_MINUTE`; the default is 10. Provider HTTP 429 responses are separately recorded in `ProviderRateLimitState` and drive durable job retry scheduling.

The application limiter is intentionally in-process. Counters reset on restart and are not shared between API replicas, so it is suitable only for the current single-instance local deployment. It is defense-in-depth against accidental repeated expensive actions, not authentication, authorization, or distributed abuse prevention. A shared limiter and complete authentication model are Sprint 5 concerns.
