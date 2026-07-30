# Worker operations

Imports are persisted in the database and are not executed by API background threads. Start one explicit worker:

```powershell
python -m packages.market_data.worker
```

Use `--once` to process at most one job, `--poll-interval 2`, `--lease-seconds 60`, `--worker-id NAME`, `--json-logs`, or `--health`. Equivalent defaults can be set with `MIL_WORKER_POLL_INTERVAL`, `MIL_WORKER_LEASE_SECONDS`, and `MIL_JSON_LOGS`.

The worker registers a stable instance row, processes due schedules, recovers expired leases, atomically claims one eligible job, renews its lease between symbol batches, records metrics/events, releases ownership, and returns to idle. Ctrl+C records a stopped worker and removes its leases. A process crash leaves the lease to expire; the next worker moves the job to retrying or dead letter according to its attempt limit and continues from the persisted symbol cursor.

The current topology is designed and tested for a single-process deployment. Database uniqueness and conditional updates prevent two workers from owning one job, but multi-host throughput, leader election, and broker-backed fairness are deferred.

In v0.5, every user schedule has a workspace and the worker copies it to each job. Workers operate with explicit system scope for shared provider/bar writes and never infer a workspace from pooled connection state. PostgreSQL CI races two claimers and verifies one lease winner; distributed fairness remains deferred.
