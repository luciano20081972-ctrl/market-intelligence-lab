# Security policy

## Deliberate trust boundary

Market Intelligence Lab v0.5.1 is an authenticated research and simulation application. It must not be used as a brokerage gateway or real-money execution system.

- No real brokerage access or Fidelity integration.
- No collection or storage of brokerage usernames, passwords, session cookies, API credentials, or two-factor codes.
- No real order submission, withdrawals, margin, options, short selling, or autonomous trading.
- No promise of returns or optimization.

## Secret handling

Configuration comes from environment variables. `.env`, secret files, credentials, local databases, logs, uploads, and runtime directories are ignored by Git. `.env.example` contains variable names and safe local examples only. System APIs return an allowlisted configuration summary and never serialize connection strings or environment values.

If a secret is accidentally committed, revoke it first, remove it from Git history using an approved incident process, and rotate any dependent credentials. Deleting only the working-tree file is insufficient.

## Threat boundaries

Supabase mode verifies asymmetric JWT signatures and required claims, then resolves application profiles and workspace membership. Workspace-owned API sessions are scoped by centralized query/write guards and permissions. CORS, trusted hosts, request limits, response headers, provider host allowlists, and redaction are defense in depth; deployment still requires TLS and a reviewed reverse proxy.

API inputs are validated with Pydantic and bounded pagination. Sort columns are allowlisted. SQLAlchemy parameterization is used instead of string-built SQL. Database uniqueness, check, foreign-key, and cascade constraints enforce invariants after application validation.

## File-upload safety

Sprint 1 has no upload endpoint. Future uploads must use size and type allowlists, generated filenames, a non-public quarantine directory, malware inspection where appropriate, and must never execute uploaded content.

## Known limitations

- PostgreSQL RLS is enabled on application tables with no browser-facing policies. This denies direct Data API rows but is not complete workspace-aware RLS; application-level tenant isolation remains mandatory and tested.
- Direct session-pooler authentication for the staging validation workstation is unresolved. Staging schema transport uses the connected, controlled Supabase integration and does not replace normal production Alembic connectivity.
- Live Supabase JWTs were validated against a temporary local application database; a live FastAPI-to-staging PostgreSQL runtime was not claimed because of the unresolved direct pooler login.
- SQLite is appropriate for local development, not an exposed multi-user service.
- Container-image signing/scanning and cryptographically tamper-evident audit storage remain future hardening.
- Audit events record application mutations but are not cryptographically tamper-evident.
- Frontend content security policy and production reverse-proxy hardening remain deployment responsibilities.

The release dependency audit is zero-known-vulnerability at validation time.
React Router is pinned to the patched 8.3.0 release, and Vitest/coverage are
pinned together at 4.1.10 so the patched glob/minimatch/brace-expansion chain
remains API-compatible. CI fails on high-or-critical npm advisories.

## Reporting

Do not open a public issue containing secrets or exploit details. Contact the repository owner privately with affected version, reproduction steps, and impact. Do not include real brokerage credentials in any report.

## Market-data provider credentials

Version 0.5.1 stores only environment-variable references in `provider_credentials`; provider secrets are never returned by the API or persisted in application tables. Stooq needs no credential. Twelve Data is disabled without `MIL_TWELVE_DATA_API_KEY` and sends it only in the recommended authorization header to its fixed HTTPS host. No commercial redistribution right is claimed.

Imported payloads are untrusted data. Normalization enforces symbols, timezone-aware provenance, OHLC and volume invariants, exchange sessions, checksums, and duplicate constraints before records become available to research workflows.
# Sprint 4 external-request controls

Stooq requests use one fixed HTTPS URL, refuse redirects, accept no user-controlled host or path, enforce a 1–60 second timeout, cap responses at 2 MB, and normalize provider errors without returning private environment values. No credential is required. Future provider keys must remain environment-only and are represented in the database by variable name/reference only.

Expensive operations have a single-instance fixed-window limiter. Authentication and user isolation are separate controls; distributed rate limiting and database-enforced audit retention remain deferred.

Worker logs redact common credential patterns. Do not include authorization headers, DSNs with passwords, `.env` contents, or provider response credentials in operational metadata.

Unexpected Stooq HTML/error bodies are untrusted and are neither persisted nor returned to the frontend. Diagnostics expose only an allowlisted classification and static safe message. HTTP 200 does not imply provider health: content type, response envelope, schema, dates, and market values must all validate before data can enter the durable pipeline.
