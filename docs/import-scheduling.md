# Import scheduling

Schedules are persisted in `import_schedules`. A schedule records provider, asset symbols, full/incremental mode, adjustment preference, IANA timezone, lookback policy, enabled state, next/last run, and failure details. Version 0.4.0 supports daily schedules and manual run-now requests.

The worker evaluates due schedules before claiming jobs. Each due time gets a `ScheduleRun` protected by a unique `(schedule_id, scheduled_for)` constraint. The derived import job also receives a deterministic idempotency key, so repeated scheduler passes or restarts cannot enqueue the same occurrence twice. The current policy uses a fixed lookback window ending at processing time; incremental ingestion advances beyond the latest stored bar.

```powershell
python scripts/operations.py scheduler
```

Timezone data is validated and stored, but cron expressions, exchange-close-relative execution, missed-run backfill policies, and distributed scheduler leadership are deferred.
