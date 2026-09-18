# MIL-AUTH-02 — native authentication validation

Implementation and local validation completed on 2026-09-18. This is readiness
for independent security validation, not production acceptance or deployment approval.
Branch: `feat/v0.15-real-market-foundation`. Starting SHA:
`bc7dc092705a5d60b16c707aefae72605a05a949`. The implementation commit containing
this report is the validation candidate; obtain its SHA with `git log -1`.

## Results

| Check | Result |
|---|---|
| Native security/identity/session suite | 46 passed |
| Same run including two production configuration regressions | 48 passed |
| Full backend | 360 passed, 20 skipped; 836.07 seconds |
| Backend combined statement/branch coverage | 83.13% |
| Critical coverage gate | 90% (80% required); native module 92% |
| Frontend regression | 92 passed in 14 files |
| Frontend coverage | Statements 70.12%, branches 66.09%, functions 55.21%, lines 75.09%; gates passed |
| Chrome native authentication acceptance | 1 passed, 6.4 seconds |
| PostgreSQL 17 native migration/cross-process test | 1 passed, 1 deselected |
| PostgreSQL 18 native migration/cross-process test | 1 passed, 1 deselected |
| PostgreSQL 17 and 18 clean upgrade, repeated upgrade, Alembic drift | PASS on both |
| SQLite native migration/preservation | PASS; included in full backend |
| Ruff | PASS |
| MyPy | PASS, 178 source files |
| TypeScript | PASS |
| Vite production build | PASS, 5.48 seconds |
| pip check / pip-audit | PASS / no known vulnerabilities (editable project skipped) |
| pnpm audit high/critical gate | PASS; two moderate development-package findings retained |
| New GitHub standard CI | Not run for this local candidate |

The 20 backend skips comprise 18 PostgreSQL-gated tests and two opt-in external
provider checks. The native PostgreSQL case was separately executed successfully
on both versions. The other legacy PostgreSQL cases were not repeated in this
continuation; their prior candidate CI evidence remains historical. No skipped
case is counted as a pass. Backend warnings were an existing Starlette/httpx
deprecation and Windows pytest-cache write permission, neither a failed test.

Local raw logs and JUnit/coverage reports are under ignored `runtime/auth02/`.
PostgreSQL command results were captured in the task tool history. No production
credentials, identities or records were used in these tests.

## Identity, migration and security evidence

Migration `a015a0020001` adds only `native_credentials`, `native_sessions` and
`auth_rate_buckets`, after `f01500000001`. Populated fixtures starting at production
revision `a141c0de0001` preserve profile IDs and external subject provenance,
workspace ownership/memberships, watchlists, strategies/versions, backtests, paper
records and prior audit events through repeated upgrade and enrollment. New audit
events are additive. Unique login assignment does not infer identity from email.
This is fixture evidence, not a production identity migration or backup rehearsal.

Tests exercise invalid credentials, weak/corrupt stored hashes, disabled users,
duplicate-email isolation, explicit enrollment, session expiry/versioning/revocation,
bounded last-seen writes and session rows, password changes/resets, generic errors,
rate limits, untrusted origins, missing origins, cookie/query rejection, body limits,
secret scrubbing, native operation without Supabase, RBAC and workspace isolation.
Fresh PostgreSQL interpreters accept a live token and reject it after revocation;
another process cannot acquire either occupied global Argon2 advisory-lock slot.

Chrome covers invalid login, login, workspace switching, protected navigation,
memory-only session storage, reload requiring sign-in, logout/token rejection,
expired-session UI and password change/operator recovery. It uses disposable
local data and generated credentials, with no traces/screenshots containing secrets.

Three proven defects were corrected during continuation: a production configuration
error-message regression; a late login restoring state after provider unmount;
and login/stale-token 401 responses incorrectly expiring browser authentication.
Their regression tests pass. No unrelated application behavior was refactored.

See [native authentication operations](native-authentication.md) for the exact
credential, session, rate, audit, enrollment, origin and rollback controls.

## Measured resources

Ubuntu validation image, one CPU quota: Argon2id 65,536 KiB, time cost 3,
parallelism 1; median 193.45 ms and maximum 194.75 ms across five hashes.
Two concurrent hashes completed in 390.18 ms. Hash-process idle RSS was 85,988 KiB,
peak 217,156 KiB: 131,168 KiB incremental (about 128.1 MiB). The PostgreSQL-backed
global concurrency cap is two, in addition to the local semaphore.

Fresh-process API idle RSS: frozen baseline 285,468 KiB, native 287,052 KiB,
difference 1,584 KiB (about 1.55 MiB). Single-run measurements contain process noise
and are not a production capacity certification. Native table/index storage for
one credential, one session and three buckets was 163,840 bytes on each PostgreSQL
version: credentials 49,152, sessions 73,728, buckets 40,960. This excludes audit
growth/backups and is not a large-user-count estimate. No additional production
service or paid dependency is required.

## Retained Supabase references

Native runtime does not use Supabase login, token issuance/refresh, recovery or
JWKS. The frontend SDK, lockfile entries, build arguments and CSP permissions were
removed. Remaining references have these explicit purposes:

| Files | Reason retained |
|---|---|
| `packages/auth/service.py`, `packages/core/config.py`, `apps/api/main.py`, `apps/api/routers/identity.py`, `.env.example` | Explicit legacy backend mode/configuration and compatibility health checks; native bypasses them |
| `scripts/provision_owner.py`, `scripts/validate_supabase_staging.py`, `deploy/compose.supabase-secret.yaml` | Legacy operator/staging tooling, not native enrollment or runtime |
| `scripts/seed_phase5_reconciliation_fixture.py`, `tests/test_migrations.py`, `tests/test_phase5_reconciliation.py`, `tests/test_private_beta_operations.py`, `tests/test_secure_platform.py`, `tests/test_system.py`, `apps/web/src/test/sprint5.test.tsx` | Historical fixture provenance and legacy compatibility tests |
| `migrations/versions/cba31be9f005_lock_down_public_data_api_access.py` | Immutable historical Data API lockdown migration |
| `packages/observability/sentry.py`, `packages/hypothesis/engines.py` | Secret redaction and credential-exclusion wording |
| `packages/world_data/object_store.py`, `docs/data/object-storage.md` | Local adapter documentation; no Supabase runtime implementation |
| `config/infrastructure-services.yaml`, `config/upstream-projects.yaml` | Infrastructure/upstream inventory |
| `README.md`, `CHANGELOG.md`, `SECURITY.md`, `docs/architecture.md`, `docs/database.md`, `docs/testing.md`, `docs/operations/authentication.md`, `docs/security/authentication.md` | Current native guidance plus retained release/architecture history |
| `docs/architecture/world-intelligence.md`, `docs/deployment/supabase-connector-deployment.md`, `docs/deployment/supabase-staging.md`, `docs/infrastructure/exit-strategy.md`, `docs/infrastructure/free-tier-services.md`, `docs/infrastructure/service-failure-modes.md`, `docs/operations/phase5-to-v0141-deployment.md`, `docs/operations/phase5-v014-reconciliation.md`, `docs/operations/production-configuration.md`, `docs/research/rd-agent-integration.md`, `docs/security/secret-management.md`, `docs/security/workspace-isolation.md` | Historical deployment, infrastructure, research and security evidence; not native runtime calls |
| New native implementation documentation/tests | Explicit assertions and explanation of dependency removal |

Production still uses its unchanged previous release; removing the candidate's
dependency does not claim production authentication is restored.

## Boundaries, risks and deferred gates

“Authorized transfer” meant only source, tests, configuration/sample fixtures and
public dependency wheels copied to the explicitly authorized Ubuntu validation
host. It included no production data, credentials or identity mutation. The earlier
automatic reviewer quota interruption was a tool-capacity stop, not a failed test;
authorized validation succeeded after capacity recovered, without bypassing review.

Both test database containers used no host ports, no network, no production mounts
and no shared production state. Both were removed with their private volumes after
validation. Validation source/image artifacts remain for review; no test service
remains running. Production container images remain v0.14.1, with all five MIL
containers healthy and unchanged two-week uptimes. Production DB revision remains
the previously verified `a141c0de0001`; no production migration was run. BACKUP READY
is preserved from prior archive verification, without repeating restore validation.

Independent security review, new standard CI, actual deployment-role privilege
checks, production-derived migration/rollback rehearsal, secure owner enrollment,
production deployment and acceptance remain deferred. Downgrade deliberately
refuses credential/session deletion; rollback needs pinned configuration/images and
a rehearsed backup/reconciliation plan. Returning to inactive Supabase cannot
restore login. Shared proxy throttling can affect legitimate users under abuse;
audit retention and browser-memory XSS exposure require review. No MFA, SSO, cookies
or registration were added.

The unchanged Vitest 4.1.10 and `@vitest/mocker` 4.1.10 development dependencies have
moderate advisory GHSA-82fw-gwwq-j7x9 (path traversal/arbitrary file read). The audit
reports a patched range starting at 4.1.11. Both versions existed in the frozen
baseline; upgrading the test framework was outside this auth correction. No high
or critical finding was reported by the audit.

Distribution license review, OPS-MIL-SUPABASE-001, the external SEC limitation and
Windows Docker Desktop tooling issue remain separately open. No material scope
deviation or destructive stop condition occurred.

Production modified: NO. Production DB modified: NO. Supabase modified: NO.
Networking modified: NO. Credentials exposed: NO. v0.15 deployed: NO.
Merge/tag performed: NO.

## Changed file inventory

- .env.example
- .github/workflows/ci.yml
- README.md
- apps/api/dependencies.py
- apps/api/main.py
- apps/api/routers/identity.py
- apps/api/routers/native_auth.py
- apps/web/Dockerfile
- apps/web/e2e-native/auth.spec.ts
- apps/web/nginx.conf
- apps/web/package.json
- apps/web/playwright.native.config.ts
- apps/web/pnpm-lock.yaml
- apps/web/src/api.ts
- apps/web/src/auth.tsx
- apps/web/src/components/Layout.tsx
- apps/web/src/pages/PasswordReset.tsx
- apps/web/src/pages/SignIn.tsx
- apps/web/src/test/native-api.test.ts
- apps/web/src/test/native-auth.test.tsx
- apps/web/src/test/sprint5.test.tsx
- deploy/compose.production.yaml
- deploy/market-intelligence-lab.env.example
- docs/architecture.md
- docs/operations/authentication.md
- docs/operations/mil-auth-02-validation.md
- docs/operations/native-authentication.md
- docs/roadmap.md
- docs/security/authentication.md
- migrations/versions/a015a0020001_native_authentication.py
- packages/auth/native.py
- packages/auth/service.py
- packages/core/config.py
- packages/database/models.py
- packages/database/phase5_reconciliation.py
- packages/database/session.py
- packages/observability/sentry.py
- pyproject.toml
- scripts/benchmark_native_auth.py
- scripts/container_start.py
- scripts/dev.py
- scripts/e2e.py
- scripts/e2e_native_auth.py
- scripts/enroll_native_user.py
- scripts/private_beta_readiness.py
- tests/test_native_auth.py
- tests/test_native_auth_migration.py
- tests/test_private_beta_operations.py
