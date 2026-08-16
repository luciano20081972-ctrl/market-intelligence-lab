# Phase-5 to v0.14.1 deployment runbook

This procedure is documentation, not deployment authorization. Never print
secret files or connection URLs. Replace `<STAMP>` with one immutable UTC
timestamp and `<RECONCILED_SHA>` with the separately approved release commit.

## Preconditions

- A new read-only production readiness audit is green.
- PostgreSQL 17 and exact legacy-upgrade PostgreSQL 18.4 CI are green.
- Local/remote ref and image tags identify the approved v0.14.1 build.
- Production remains at known source `577b66d...`, revision `3b2f6c7d8e90`,
  and has no unexpected changes.
- `python -m scripts.phase5_reconciliation_check --json` reports
  `RECONCILIATION_REQUIRED`, not `INCOMPATIBLE`.
- IAmGodTranslator is healthy and its port-443 route is recorded.

## Pre-flight snapshot

On the server, set `STAMP=$(date -u +%Y%m%dT%H%M%SZ)` and create
`/srv/backups/market-intelligence-lab/$STAMP` with mode 0700. Using the existing
protected database URL file without echoing it:

1. Create a PostgreSQL custom-format dump named `database.dump`.
2. Snapshot `/srv/data/market-intelligence-lab/raw` as `raw-objects.tar`.
3. Copy the protected MIL Compose and configuration into an encrypted or
   root-only archive; never include secret contents in the manifest.
4. Save `docker inspect` image IDs/digests, current Git SHA, Compose checksum,
   sanitized configuration checksum, and `tailscale serve/funnel status --json`.
5. Run `python -m scripts.private_beta_backup` with the recorded checksums,
   image digests, Git SHA, and route-state reference; save its JSON manifest.
6. Generate SHA-256 sums for every backup artifact and make them root-readable only.
7. Confirm IAmGodTranslator remains healthy. Do not change its Compose or route.

Restore `database.dump` and raw objects into disposable PostgreSQL 18.4 and a
disposable object path. Run reconciliation, compare counts/checksums and owner
linkage, run Alembic/readiness checks, and mark the manifest VERIFIED. A backup
that has not passed this restore is not a rollback source.

## Migration rehearsal

Against the disposable restore, in the approved v0.14.1 image:

```sh
python -m scripts.phase5_reconciliation_check --json --snapshot-output phase5-before.json
alembic upgrade head
alembic upgrade head
alembic current
alembic heads
alembic check
python -m scripts.phase5_reconciliation_check --require-head --json --compare-snapshot phase5-before.json
python -m scripts.private_beta_readiness --json
```

Require target `a141c0de0001`, one head, zero orphan counts, unchanged table
counts/checksums, and unchanged profile/Supabase-subject/workspace/owner linkage.
Do not stamp.

## Build

Fetch the approved ref normally without rewriting history. Check it out in a
separate clean deployment worktree if the current divergent checkout cannot
fast-forward. Build unique immutable tags such as
`mil-api:0.14.1-<shortsha>` and `mil-web:0.14.1-<shortsha>` using
`deploy/compose.production.yaml`. Retain these rollback images:

- `mil-api:0.11.0-466cb8b`
- `mil-api:0.11.0-35f145d`
- `mil-web:0.11.0-577b66d`

Inspect the built frontend for service-role/secret-key/database/private-key
patterns. Verify production configuration rejects missing project reference,
disabled auth, wildcard origins/hosts, SQLite, and ephemeral storage.

## Approved production change

1. Reconfirm the source SHA, database revision, fresh verified backup, image
   digests, route state, free resources, and translator health.
2. Enter documented MIL maintenance mode; leave health/readiness available.
3. Stop only legacy `mil-supervisor` and MIL write workers. Do not stop Caddy,
   PostgreSQL, Tailscale, or IAmGodTranslator.
4. Run the reconciliation check and require `RECONCILIATION_REQUIRED`.
5. Run `alembic upgrade head` once from the approved v0.14.1 image.
6. Require `alembic current` and the reconciliation check to report
   `a141c0de0001` / `RECONCILED`.
7. Apply the reviewed production Compose with only API, web, market-data worker,
   scheduler, and operations worker. Do not recreate unrelated services.
8. Keep the supervisor retired. Never run it concurrently with the scheduler
   or operations worker.
9. Exit maintenance only after all post-deployment checks pass.

## Post-deployment verification

Require healthy API/web containers; database/readiness endpoints; private and
approved HTTPS routes; sign-in; authenticated `/api/v1/auth/me`; linked owner
profile/workspace/membership; unauthenticated 401; market-worker, scheduler and
operations-worker heartbeats; persistent raw/backup mounts; Operations Center;
forecast/prospective workflows; and paper-only rejection of live execution.
Confirm legacy counts and identity checksum again. Run only separately approved
bounded provider smoke tests. Confirm IAmGodTranslator and its private 443 route
remain unchanged.

After explicit approval, reboot once and verify Docker restart policies,
heartbeats, lease recovery, duplicate prevention, routes, storage, and both
applications. Repeat a disposable restore drill using the deployed backup.

## Rollback

This release uses **FORWARD MIGRATION + SNAPSHOT RESTORE ROLLBACK**. Do not run
`alembic downgrade` and do not stamp.

1. Re-enter maintenance and stop only new MIL web/API/workers/scheduler.
2. Preserve post-failure logs and a diagnostic database snapshot separately.
3. Restore the exact verified pre-deployment `database.dump` and raw-object
   snapshot identified by `<STAMP>`.
4. Restore the captured protected configuration and old Compose.
5. Recreate only MIL using the recorded old image IDs/tags.
6. Restore the recorded Serve/Funnel state only if it changed during the
   separately approved deployment; never alter IAmGodTranslator's port 443.
7. Verify old database revision `3b2f6c7d8e90`, API/web/auth/owner/workspace,
   worker/supervisor, storage, and IAmGodTranslator health.
8. Keep the failed v0.14.1 images and diagnostics for investigation.

Rollback is not authorized unless the manifest names a fresh VERIFIED backup
and exact old image digests.
