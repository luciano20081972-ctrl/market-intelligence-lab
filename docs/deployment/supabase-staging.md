# Supabase staging

The staging project uses PostgreSQL 17 and Supabase Auth. Backend-only settings include the project reference, runtime/migration database URLs, JWT audience, and secret key. Frontend configuration is limited to `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`; no backend secret may use a `VITE_` prefix.

Local secret configuration and the trusted CA are ignored and must never be printed, committed, embedded in build output, or copied into issue reports. PostgreSQL connections require certificate verification with `PGSSLMODE=verify-full` and the configured `PGSSLROOTCERT`. Runtime and migration URLs are separate, and SQLAlchemy normalizes plain PostgreSQL URLs to the installed psycopg v3 dialect.

For v0.5.1 staging, follow [the connector deployment procedure](supabase-connector-deployment.md). The direct pooler login remains a known workstation limitation, so connector deployment is the controlled staging exception. Normal environments should execute the canonical chain with `alembic upgrade head`.

## Validation

- Confirm liveness and readiness separately. Staging/production readiness fails when the database is unreachable or `alembic_version` differs from the expected revision.
- Verify JWKS reachability and live issuer, audience, expiry, subject, refresh, and sign-out behavior with temporary identities.
- Verify direct REST access is denied for both publishable-only and authenticated browser roles.
- Verify the PostgreSQL owner/backend retains access. This role bypasses ordinary RLS as table owner; it must never be exposed to a browser.
- Remove temporary validation users and application rows after sign-out/session revocation where supported.

The v0.5.1 rehearsal reached Alembic revision `4a2523700bdb` with 47 application
tables, all 47 RLS-enabled, zero RLS policies, zero direct table/function grants
to `anon` or `authenticated`, zero missing foreign-key indexes, and zero
application rows. Two temporary confirmed Auth users exercised password sign-in,
asymmetric-JWKS validation, claim validation, refresh, sign-out, refresh
revocation, and application authorization; connector verification confirmed that
both users were deleted. Run `python scripts/validate_supabase_staging.py` only
with the ignored staging configuration and explicit live-test flag.

The Supabase security advisor reports one informational `rls_enabled_no_policy`
notice per application table. That is expected for this release's deliberate
deny-by-default design and must not be represented as workspace-aware RLS.
Performance advisor unused-index notices are also expected before staging has
representative traffic; they are not evidence that required constraint/query
indexes should be removed.

## Logical backups

Do not claim Supabase backups exist until plan settings and a successful restore are independently verified. These Windows-compatible procedures apply when authorized direct database access is available:

1. Store non-secret connection parameters in a restricted libpq service file and the password in a separate restricted password file. Use Windows ACLs so only the operator account can read either file.
2. Set `PGSERVICE`, `PGSERVICEFILE`, and `PGPASSFILE` in the current PowerShell process. Do not place credentials on a command line.
3. Schema-only export: `pg_dump --format=custom --schema-only --file staging-schema.dump`.
4. Full logical export: `pg_dump --format=custom --no-owner --no-acl --file staging-full.dump`.
5. Encrypt immediately with an approved interactive encryption tool; remove the plaintext only after verifying the encrypted copy and recording its checksum.
6. Store encrypted copies in an off-provider, access-controlled location. A practical baseline is daily copies for 14 days, weekly copies for 8 weeks, and monthly copies for 12 months, adjusted to legal and business requirements.
7. Restore only into disposable PostgreSQL 17: create an empty database, run `pg_restore --exit-on-error --no-owner --no-acl`, then verify `alembic_version`, table/constraint counts, representative UUID/numeric/timestamptz values, and application row counts.
8. Record restore date, source checksum, PostgreSQL version, operator, outcome, and deletion date without recording credentials.

Never commit dump, backup, log, certificate, or generated restore files.
