# Scheduler

`python -m packages.operations.scheduler` materializes persisted task definitions into unique
occurrences. PostgreSQL claims due definitions using row locks and `SKIP LOCKED`; the unique
`(definition_id, scheduled_for)` constraint is the final duplicate barrier. Heartbeats and leases
expire, allowing another instance to recover work. Supported schedules are INTERVAL, DAILY,
WEEKLY, MARKET_CALENDAR, and DATASET_CADENCE. Shutdown stops new claims and records OFFLINE.
