# Phase-5 to v0.14.1 reconciliation

## Evidence and lineage

The production-only line and official line share commit
`deb819577ccfd364e7b67bb328a89d261f25c539`. Production source
`577b66da0762dd611f3c98d86801fcd8adc445bb` contains Phase-5 commit
`35f145dca796d4d9391d6ea86799efd3f8683c1e`; it is not an ancestor of official
v0.14.0. The database genuinely ran revision `3b2f6c7d8e90`, whose parent is
`ed23735efb90`. Official history instead proceeds from `ed23735efb90` through
`eb1ff477509f`, `e2517ff0412b`, `4e398fc4c9a1`, and `5595df1fe1cf`.

The original `3b2f6c7d8e90` definition is retained as the **legacy Phase-5
production history**. Revision `a141c0de0001` joins that head and official head
`5595df1fe1cf`. No stamp or direct `alembic_version` manipulation is permitted.

## Legacy schema inventory and disposition

All timestamps use the project UTC type. All UUID identifiers are preserved.

| Table | Important columns and conventions | Keys, constraints, and indexes | Disposition |
|---|---|---|---|
| `compute_jobs` | workspace/requester, submission key, job type/class, priority, state, deadline, symbols/date range, parameters and version fields, input/data/checkpoint/result manifests, estimates/costs, provider/execution, attempts/errors, lifecycle timestamps | PK `id`; FK workspace CASCADE and requester RESTRICT; unique workspace/submission and cloud execution; class/state/range/cost checks; generated lookup indexes plus workspace/state/priority | `PRESERVE_LEGACY`; future optional read-only export |
| `compute_job_transitions` | job, from/to state, reason, details, created time | PK; FK job CASCADE; job/state/time and job/time indexes | `PRESERVE_LEGACY` with parent compute job |
| `cloud_usage_ledger` | workspace/job/provider, estimated and observed cost, task count, usage date | PK; workspace CASCADE, job SET NULL; nonnegative cost and positive task checks; workspace/job/provider/date indexes | `PRESERVE_LEGACY`; cloud execution remains disabled |
| `market_supervisor_heartbeats` | instance, market session, cloud flag, provider/scheduler state, scan/error/heartbeat/start times | PK; unique instance index; session and heartbeat indexes | `PRESERVE_LEGACY`; supervisor retired after cutover |
| `data_freshness_observations` | workspace, source/symbol, market/receive/process times, age, classification, details | PK; workspace CASCADE; REAL_TIME/DELAYED/STALE/UNKNOWN check; workspace/source/symbol/time/classification indexes | `MAP_TO_V014` conceptually; retain rows, use `data_freshness_statuses` for new state |
| `decision_signals` | workspace/symbol, BUY/SELL/HOLD/WATCH/AVOID decision, confidence, horizon/regime/evidence/risk/freshness/version/manifest | PK; workspace CASCADE; action/confidence checks; lookup indexes | `PRESERVE_LEGACY`; official prospective/paper models supersede new writes |
| `alert_events` | workspace/category/severity/deduplication/title/message/payload/channel/status/count/times | PK; workspace CASCADE; unique workspace/dedupe; status/count checks; lookup indexes | `MAP_TO_V014` conceptually; retain rows, use `operational_alerts` for new alerts |

No table is removed in v0.14.1. `SAFE_TO_REMOVE_LATER` applies only after a
separately approved archival/export exercise proves retention requirements.
Alembic drift deliberately ignores these reflected legacy tables because they
are retained history, not active ORM models.

## Preservation policy and verification

- `user_profiles`, `workspaces`, and `workspace_memberships` are on the shared
  ancestor and are never rewritten by reconciliation. Supabase subject, email,
  owner role, workspace ID, and audit history remain unchanged.
- Compute jobs, transitions, usage, supervisor history, freshness observations,
  decision signals, and alerts remain in their original tables without updates.
- Before and after migration, record per-table counts, identity-linkage checksum,
  and orphan counts. `python -m scripts.phase5_reconciliation_check --json`
  performs this inspection without writes or credential output.
- Required invariants: zero orphan compute workspaces, users, or transitions;
  unchanged owner/profile/workspace linkage; no duplicate identifiers; every
  legacy table and required column remains present.
- Rollback is **FORWARD MIGRATION + SNAPSHOT RESTORE ROLLBACK**. The merge
  revision intentionally rejects downgrade because reversing both histories
  would risk deleting production information.

## Compute disposition

| Capability | Disposition | Reason |
|---|---|---|
| Resource estimation and local capacity guard | `ALREADY_REPLACED` | v0.14 resource budgets and backpressure govern approved workers |
| Durable job history/manifests | `STILL_USEFUL` as retained data | Preserved read-only for audit and future export |
| Cloud Run/Google Batch orchestration | `FUTURE_OPTIONAL` | Not required for private beta; adds credentials, spend, and failure surface |
| Sharding/cloud worker image | `OBSOLETE` for this release | No approved private-beta dependency |
| Automatic cloud routing | `UNSAFE` unless separately authorized | Cloud execution and spend remain disabled |
| Paper/live safety guard | `ALREADY_REPLACED` | Current prospective and paper-only boundaries reject brokerage execution |

No `packages/compute`, Phase-5 API, cloud SDK, or cloud credential surface is
ported into v0.14.1.

## Supervisor disposition

The Phase-5 supervisor combined market-session classification, provider
freshness, alert deduplication, decision-signal filtering, compute routing, and
a heartbeat loop. Final ownership is:

| Legacy responsibility | v0.14.1 owner |
|---|---|
| Provider import execution | market-data worker |
| Due-time and market-calendar scheduling | scheduler |
| Freshness evaluation and operational alerts | operations worker |
| Durable health/heartbeat reporting | scheduler, worker, and health endpoints |
| Compute/cloud routing | retired; cloud remains disabled |
| Decision-signal generation | official prospective/paper workflow, manual/simulated only |

The final topology is API, web, market-data worker, scheduler, and operations
worker. Do not run `mil-supervisor` beside scheduler/operations-worker: that
would duplicate freshness, alert, and scheduling activity. Preserve its tables,
stop it only inside an approved maintenance cutover, and retain its old image
for snapshot-based rollback.

## Provider policy

- SEC: disabled until a compliant identifying User-Agent is configured.
- FRED/ALFRED and EIA: disabled unless credentialed and explicitly approved.
- Twelve Data: disabled unless credentialed and explicitly approved.
- Stooq: `DEGRADED` or `DISABLED_FOR_PRIVATE_BETA` until its HTML/access-page
  behavior passes strict CSV validation. Do not weaken validation and do not
  make it a global readiness dependency.
- Synthetic: fixture/test only.

Readiness distinguishes intentionally disabled optional providers from a broken
provider designated as required.
