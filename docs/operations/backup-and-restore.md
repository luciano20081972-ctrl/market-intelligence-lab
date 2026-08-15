# Backup and restore

`python -m scripts.private_beta_backup` prints a dry-run, timestamped, secret-free manifest. An
approved deployment backup uses PostgreSQL `pg_dump` in custom format plus a filesystem snapshot of
the raw-object root. Store SHA-256 checksums, version, Alembic revision, configuration-template
version, and references—not secrets—in the manifest.

Restore only into a disposable database and object path. Run `pg_restore`, upgrade/check Alembic,
compare critical record counts and checksums, verify representative research lineage, then record a
VERIFIED restore result. Never test destructive restoration against production.
