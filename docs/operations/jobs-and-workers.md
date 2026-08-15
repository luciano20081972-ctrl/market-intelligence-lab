# Jobs and workers

Operational occurrences use QUEUED, CLAIMED, RUNNING, SUCCEEDED, RETRY_WAIT, FAILED,
QUARANTINED, and CANCELLED. Existing imports retain their compatible durable state machine.
Claims have owners and expirations; expired work is retried or quarantined without deleting error
history. Retry categories separate transient network/rate-limit/5xx/timeout/database failures from
authentication, schema, invalid-response, and permanent-validation failures. Backoff is bounded,
jittered deterministically, and honors bounded Retry-After values.

`python -m packages.operations.worker` claims only registered task types. The initial built-in task
recomputes data freshness and alerts; an unknown task is quarantined rather than dynamically
imported or executed. Existing import work remains in `packages.market_data.worker`.
