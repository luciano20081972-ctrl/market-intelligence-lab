# Supabase connector deployment

Alembic files in `migrations/versions` remain the canonical application schema history. For the v0.5.1 staging validation only, the connected read/write Supabase database tool is the SQL transport because direct session-pooler password authentication from the validation workstation remains unresolved. This transport does not replace ordinary Alembic execution for production or disaster recovery.

## Revision mapping

Apply one transaction-scoped connector batch per canonical revision, in this order:

1. `0001_foundation` — foundation market-data, watchlist, audit, and source tables.
2. `0002_backtesting_paper_trading` — strategy, backtest, signal, and simulated-paper tables.
3. `10fdd3577a14` — historical provider, calendar, metadata, corporate-action, and import tables.
4. `1a52c2d25013` — operational queues, workers, leases, schedules, reconciliation, and provenance columns.
5. `18cca98a50d5` — identity/workspace schema and workspace ownership columns.
6. `cba31be9f005` — PostgreSQL Data API privilege and RLS lockdown.
7. `4a2523700bdb` — indexes for the four source price-bar foreign keys.

Each batch name includes its Alembic revision. The SQL includes the corresponding `alembic_version` insert/update, and post-batch verification reads that table. `supabase_migrations.schema_migrations` may record connector transport calls but is never used as application migration authority.

## Clean-staging translation

The repository’s `18cca98a50d5` data migration creates a deterministic legacy development identity/workspace so existing installations can acquire non-null workspace foreign keys. The validated staging schema is empty. Its connector batch therefore omits those three development bootstrap inserts and their row-update statements, while applying the exact final table, column, index, constraint, and `alembic_version` state. The batch must first prove all affected tables are empty. This is a clean-database data-migration precondition, not an independent schema design.

No batch may seed providers, users, workspaces, demonstrations, tests, or generated identifiers. No batch references `auth`, `storage`, `realtime`, `vault`, `extensions`, or other Supabase-managed schemas.

## Safety procedure

1. Confirm the project is healthy, PostgreSQL is 17, `public` has no application tables, and no `public.alembic_version` exists.
2. Render and review PostgreSQL SQL from the matching Alembic revision.
3. Reject SQLite table-copy SQL, downgrade/drop SQL, extension-version pins, unmanaged-schema references, or a revision mismatch.
4. Apply one revision transaction. Stop on the first error; do not continue or improvise.
5. Verify the expected `alembic_version`, expected objects, and unchanged managed-schema inventory.
6. After the last revision, verify constraints, foreign-key indexes, UUID/numeric/timestamptz types, zero application rows, RLS flags, policy count, role privileges, and default privileges.
7. Re-run only read-only verification. Idempotence means the final state remains correct; it does not mean replaying non-idempotent `CREATE TABLE` batches.

Downgrades contain destructive drops and are not used on staging. The v0.5.1 privilege migration intentionally does not restore unknown prior grants during downgrade.
