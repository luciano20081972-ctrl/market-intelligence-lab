# Import job state machine

The normal path is `queued → running → succeeded`. A retryable provider failure moves `running → retrying`; after `next_retry_at`, a worker may move it back to `running`. Exhausted or explicitly permanent failures become `failed` or `dead_letter`. A lease-expired running job becomes `retrying` when attempts remain and `dead_letter` otherwise. Queued/running/retrying jobs accept cancellation requests; a queued job becomes `cancelled` immediately while a running worker observes the flag between batches. Failed, interrupted, retrying, and cancelled jobs may be manually requeued.

Every API acceptance, claim, cancellation, lease expiry, retry, and completion writes a `JobEvent`. A unique `JobLease.job_id` plus a conditional status update establishes single ownership. The lease token is random, expires at a persisted UTC timestamp, and is renewed by the owning worker. `resume_cursor.symbol_index` advances only after a successful batch.

Terminal states are `succeeded`, `failed`, `cancelled`, and `dead_letter`. Existing price records are never removed by state recovery.
