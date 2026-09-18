# Native authentication — MIL-AUTH-02

The v0.15 corrective implementation uses existing PostgreSQL for credentials,
opaque sessions and shared throttling. It does not require Supabase Auth, JWKS,
refresh or recovery in `MIL_AUTH_MODE=native`. Production remains v0.14.1 until a
separately authorized deployment and owner enrollment. The frozen market-data
baseline is `bc7dc092705a5d60b16c707aefae72605a05a949`.

## Identity and schema

Migration `a015a0020001` follows `f01500000001`. It only adds
`native_credentials`, `native_sessions` and `auth_rate_buckets`. Application user
IDs, workspace IDs, memberships, ownership and application foreign keys are not
rewritten. `user_profiles.auth_subject` remains historical provenance. Login is
an explicitly assigned unique normalized identifier, not inferred from email.

Native tables have named constraints/indexes under the existing naming convention.
PostgreSQL tables enable RLS and revoke PUBLIC/anon/authenticated access. They are
server-only; no Data API policy grants are introduced. The eventual deployment
rehearsal must verify the actual migration/runtime role privileges.

## Configuration

Set `MIL_AUTH_MODE=native`, `MIL_EXPECTED_SCHEMA_REVISION=a015a0020001`, persistent
PostgreSQL, exact `MIL_AUTH_ALLOWED_ORIGINS` and restrictive `MIL_CORS_ORIGINS`.
Production origins must use HTTPS; wildcard, path-bearing and missing origins
are rejected. For the existing MIL exposure the origin includes `:8443`.
The checked-in production environment example contains the exact existing origin.
No Caddy, Tailscale, Funnel, DNS or Docker-network changes are needed.

Defaults: idle expiration 1,800 seconds; absolute expiration 28,800 seconds;
last-seen writes at most once per 60 seconds per session. The touch interval can
make an idle timeout conservative by up to that interval. Idle expiry never
extends past absolute expiry. Production cannot fall back to disabled auth.
The disabled browser path also requires an explicit development-build setting.

The supported browser path is HTTPS through the existing proxy. Origin validation
is not proof of transport encryption for arbitrary non-browser clients. Direct
unencrypted access is not a supported credential transport. Forwarded headers are
not trusted by the application launchers; source throttling deliberately groups
clients behind the existing proxy instead of trusting a spoofable client IP.

## Credentials and sessions

`argon2-cffi==25.1.0` supplies Argon2id: 65,536 KiB, three iterations, parallelism
one, 32-byte hash, random salt. Parameters are not weakened for tests. Login
rejects stored hashes outside the approved policy. Passwords are 15–128 characters.

Opaque tokens use `secrets.token_urlsafe(32)` (256 bits of entropy). Only SHA-256
digests are stored. Each request checks the current database session, expiry,
revocation, credential version and enabled local profile, then uses existing RBAC.
At most ten session rows per user survive successful-login cleanup; expired rows
are also removed. Logout revokes the session; password change/reset increments
the credential version and revokes all sessions for that user.

The browser holds the bearer token only in memory. Reload/reopen requires another
sign-in. Workspace preference alone may remain in localStorage. Fetch omits cookies.
Credentials in cookies/query parameters and unsupported origins are rejected.
Auth responses are not cached. Late login/401 responses cannot restore or expire
a different browser session.

## Abuse controls and audit

Fixed 60-second windows default to 10 account attempts, 30 source attempts and
60 global attempts. Account/source keys map to 4,096 slots each, plus one global
row: at most 8,193 possible bucket keys. Expired buckets are deleted during
admission. Slot collisions conservatively share a limit; they never bypass it.
Windows expire rather than imposing permanent account lockouts. Sustained public
traffic can still consume the shared proxy/global budget.

Two concurrent Argon2 operations are permitted per process. PostgreSQL transaction
advisory locks also cap hashing across API processes. SQLite uses only the local
gate and is for disposable/development tests, not production.

Server-authored events cover enrollment, admitted login outcomes, logout,
password changes/resets and session revocation. Rate-rejected requests do not
generate an unbounded audit event per request. Ordinary audit retention remains
an operational concern; the auth-table storage estimate excludes accumulated
audit events and backups.

Passwords, hashes and tokens are not logged. Auth validation errors omit request
inputs. SQLAlchemy hides parameters; application HTTP access logs are disabled;
Sentry drops auth request events, strips query data and disables local-variable
capture. Historical client-auth audit submissions are unavailable in native mode.

## Enrollment and recovery

Only a later explicitly authorized operator action may enroll production. Never
send credentials through ChatGPT/Codex or pass passwords in CLI arguments.

The secure-terminal command is:

```text
python -m scripts.enroll_native_user --user-id EXISTING_PROFILE_UUID --login ASSIGNED_LOGIN
```

It requires native configuration, an existing enabled profile, collision checks
and hidden password/confirmation input. It creates no profile/workspace/membership
and never links accounts by email. Existing credentials require explicit `--reset`;
reset revokes prior sessions and records audit events. Non-interactive password
input is refused. No production enrollment was performed for MIL-AUTH-02.

Recovery is operator-assisted. There is no open registration, email recovery
infrastructure, MFA, SSO, OAuth or persistent cookie in this scope.

## Verification and rollback

`tests/test_native_auth.py` covers credential/session/security/RBAC behavior.
`tests/test_native_auth_migration.py` populates old-revision identity, ownership,
watchlist, strategy/version, backtest, paper and audit fixtures, verifies repeated
upgrade/drift/names and preserves all old records after enrollment. Its PostgreSQL
test requires an empty database named `mil_auth02_*` and an explicitly configured
`MIL_NATIVE_AUTH_TEST_DATABASE_URL`; fresh interpreters prove revocation and
cross-process hash limiting. PostgreSQL 17 and 18 are the validation matrix.

`python -m scripts.e2e_native_auth` uses generated in-memory credentials, a
temporary local database and local Chrome/API/web processes. It does not connect
to production. Browser traces, screenshots and videos are disabled for auth tests.
`python -m scripts.benchmark_native_auth` measures bounded hashing; its API modes
measure idle RSS in separate processes. Results are measurements of a particular
host/run, not universal guarantees.

Do not automatically downgrade this migration: doing so would delete credentials
and sessions. Its downgrade fails explicitly. Rehearse pinned images/configuration
and a fresh backup before deployment. Old images also enforce schema revisions;
an additive migration alone does not prove rollback compatibility. Restoring a
pre-change backup after new writes requires reconciliation to avoid data loss.
Returning to the inactive Supabase dependency does not restore authentication.

## Retained Supabase references

The backend verifier/settings, owner-linking and live-staging scripts, compatibility
tests and optional secret compose remain for historical/explicit legacy use. They
are not invoked by native authentication. Historical migrations retain portable
Data API lockdown behavior. Infrastructure catalogs and earlier deployment,
architecture, staging and research documents preserve prior-release evidence.
Local raw-object storage's adapter documentation and secret-redaction/credential
guard references are not Supabase runtime dependencies. The frontend SDK, lockfile
entries, build arguments and CSP network permissions have been removed.

The previous candidate CI is historical evidence only. A new standard GitHub CI
run and independent security validation remain separate from local acceptance.
