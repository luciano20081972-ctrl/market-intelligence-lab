# Workspace authorization boundaries

HTTP workspace operations require authenticated membership and the action's
existing permission. Unknown mutation routes deny access, including for owners.
Direct resources are discovered from mapped `workspace_id` columns; scoped
sessions filter reads and ORM bulk updates/deletes and reject foreign object
flushes or reassignment. Nullable system ownership is not tenant-wide access.

Child resources must be authorized through an explicit authoritative parent.
Absence of `workspace_id` does not make a child global. New API exposure requires
classification and a negative cross-workspace persistence/read test; do not infer
ownership recursively from arbitrary foreign keys.

## Recovery and import children

`JobLease.job_id -> ImportJob.workspace_id` authorizes abandoned-job recovery.
The HTTP endpoint requires `recovery.manage` and supplies the authenticated
workspace session. Its candidate query joins the parent before any mutation.
PostgreSQL locks candidate leases with SKIP LOCKED; a conditional delete claims
each still-expired lease once before updating its job and emitting an event.

Worker instances are global processes, not permanent tenant-owned records. A
recovered lease may mark its worker unavailable only while `current_job_id`
still equals the recovered parent. An old lease cannot clear a worker's newer
assignment. The HTTP worker list exposes only current jobs in the authorized
workspace; aggregate infrastructure heartbeat health remains system information.

The internal worker creates trusted unscoped sessions and continues to recover
all workspaces. Never pass an unscoped session to the HTTP recovery operation or
grant workspace admins global worker authority.

`ImportError.job_id -> ImportJob.workspace_id` scopes both rows and pagination
totals, including requests specifying a foreign job ID. Error messages and record
identifiers must not leak across workspaces. Import batches and job events are
accessed only after their parent job is authorized. Schedule runs similarly follow
an authorized import schedule.

## Adjacent resource classification

| Resource | Classification / API boundary |
|---|---|
| ImportJob, ImportSchedule, task definitions/occurrences | Direct workspace scope |
| JobLease | Derived scope through ImportJob; no standalone HTTP CRUD |
| ImportError, ImportBatch, JobEvent | Derived scope through ImportJob |
| ScheduleRun | Derived scope through authorized ImportSchedule |
| WorkerInstance | Global process; current job association is derived scope |
| OperationalMetric | Internal worker measurements; no direct API route found |
| PaperPortfolio, PaperPortfolioPlan | Direct workspace scope |
| PaperOrder, PaperFill, PaperPosition, PortfolioSnapshot, RiskRule | Derived through PaperPortfolio; routes authorize portfolio first |
| `/paper/plans` | Body-only simulation preview and empty list; no persisted plan mutation route |
| SchedulerHeartbeat, MaintenanceState, BackupManifest | Global infrastructure state; aggregate status endpoints |
| PriceBar and market reference records | Shared market data; import-job FK is provenance, not ownership |

This bounded inventory is not a security certification of all research tables.
Unclassified future resources must remain unexposed until ownership is established.

## Verification

`tests/test_workspace_authorization.py` uses real native sessions, independent A/B
memberships, known foreign IDs, before/after snapshots, mixed recovery, reassigned
workers, concurrent actions, stale-role sessions and controlled database outages.
Trusted global recovery has a separate positive test.

The normal engine fixture uses SQLite. Explicit `MIL_AUTH04_DATABASE_URL` switches
engine-fixture tests to PostgreSQL only for the disposable database `mil_auth04b`;
each test creates, seeds and removes its own random schema. Migration validation
uses its separate existing disposable native-auth database contract.

No schema migration, redundant tenant column, new service or dependency is needed.
Independent security revalidation of the final corrective SHA remains mandatory.
