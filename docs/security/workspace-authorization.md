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

### Import manifests and HTTP parent lookup (AUTH-06)

DataManifest is parent-derived through `job_id -> ImportJob.workspace_id` for
workspace HTTP access. List, optional job filter, detail, and datasource health
use the same parent-joined query. A foreign/nonexistent manifest returns generic
404; foreign/nonexistent job filters return an empty list/count. A manifest with
no surviving import parent is not exposed to workspace HTTP clients, including
rows orphaned by `ON DELETE SET NULL`. Null ownership does not grant global access.
Trusted ingestion can still persist/read system manifests internally. Canonical
macro/energy observations remain shared; no storage or provider change is made.

HTTP import-job lookups use `get_import_job` to resolve the scoped parent and
return a controlled 404 before child traversal. Job events/quality reports and
management routes share that lookup. Invalid UUIDs remain validation errors;
other domain failures are not broadly converted to not-found responses.

Bounded import-family inventory: ImportJob/ImportSchedule are DIRECT; DataManifest,
ImportBatch, ImportError, JobEvent, JobLease and ScheduleRun are PARENT-DERIVED.
WorkerInstance is GLOBAL/SYSTEM with a parent-derived current-job view. PriceBar
is shared canonical data whose import FK is provenance, not ownership.
OperationalMetric has no direct HTTP route. RawDataObject/IngestionCheckpoint are
internal storage/checkpoint records, not exposed by these import HTTP routes.

## Adjacent resource classification

### Related-resource visibility (AUTH-08)

Authorization of A never authorizes disclosure of workspace-scoped B merely
because A references B. An HTTP response must not expose B's identifier, metadata,
count, status, nested object, lineage or provenance unless the requester is
independently authorized to know B, or the field is explicitly safe GLOBAL/SYSTEM
metadata. Possession of a foreign key is not authorization. Serialization is part
of the authorization boundary.

RELATED-RESOURCE supplements DIRECT, PARENT-DERIVED and GLOBAL/SYSTEM: it describes
an independently protected target referenced by an otherwise authorized object.
`apps/api/import_visibility.py` resolves explicit import-family visibility paths
through the same request-scoped session. It selects IDs in batches of at most 500,
not one lookup per serialized row. It is not a recursive FK authorization engine.

The HTTP representation uses null for inaccessible scalar references, including
null/orphan parents. Stored relationships and trusted ingestion remain intact.
Same-workspace references remain visible. A nonexistent manifest parent cannot be
inserted with the FK enabled; deleting a referenced parent is RESTRICTed. Losing
the parent's owning job is representable and must hide that parent reference.

| Import-family field / output | Classification / disclosure rule |
| --- | --- |
| ImportJob.id, ImportSchedule.id, job/history/status/count | DIRECT; scoped resource and action permission |
| Manifest.job_id | PARENT-DERIVED; surviving owning-job join before HTTP exposure |
| Manifest.parent_manifest_id | RELATED-RESOURCE; independently visible manifest or null, shared list/detail serializer |
| Macro/EnergyObservation.manifest_id, macro as-of output | RELATED-RESOURCE; independently visible manifest or null; canonical values/counts remain GLOBAL and unchanged |
| Datasource-health latest_manifest_id/count/timestamps | PARENT-DERIVED; latest authorized manifest only; no raw lineage field |
| ImportError.job_id and row/count | PARENT-DERIVED; joined owning job |
| ImportError.batch_id | RELATED-RESOURCE; batch's own job must be visible, otherwise null |
| Job detail batches and batch IDs | PARENT-DERIVED; job authorized first, collection constrained by that job |
| Job events/quality report | PARENT-DERIVED; job authorized first; reviewed producers emit own diagnostics/counts and GLOBAL provider/worker labels, not other tenant IDs |
| ScheduleRun.job_id in run-now response | RELATED-RESOURCE; independently scoped job or null; authorized schedule alone is insufficient |
| Worker current_job_id, worker list/count | PARENT-DERIVED current association; existing joined scoped job |
| Recovery returned job IDs/count | PARENT-DERIVED scoped leases/jobs, management permission; trusted global worker remains internal |
| Provider IDs/codes, source/dataset definitions, canonical series IDs | GLOBAL reference metadata, not private execution ownership |
| PriceBar.import_job_id | Internal provenance; price HTTP serializer does not expose it |
| Raw objects/checkpoints, leases, operational metrics, SEC parse children | No standalone import HTTP serialization of their raw related IDs found |

The bounded audit covers these import/manifest HTTP fields and the world-data
observation serializers that directly expose DataManifest references. It does
not certify independent research/backtest lineage documents or every scheduler
relationship; those domains are not broadened into this corrective task. New
fields and new consumers require explicit classification and adversarial tests,
including nested JSON: arbitrary diagnostic strings are not automatically safe
relationship containers.

`tests/test_import_relationship_visibility.py` retains same/foreign/null/orphan
lineage, FK integrity, batch/job secondary references, canonical observation
provenance, unchanged database snapshots and a bounded-query-count check.

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
