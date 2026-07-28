# Security policy

## Deliberate trust boundary

Market Intelligence Lab v0.2.0 is a local research and simulation application. It must not be used as a brokerage gateway or real-money execution system.

- No real brokerage access or Fidelity integration.
- No collection or storage of brokerage usernames, passwords, session cookies, API credentials, or two-factor codes.
- No real order submission, withdrawals, margin, options, short selling, or autonomous trading.
- No promise of returns or optimization.

## Secret handling

Configuration comes from environment variables. `.env`, secret files, credentials, local databases, logs, uploads, and runtime directories are ignored by Git. `.env.example` contains variable names and safe local examples only. System APIs return an allowlisted configuration summary and never serialize connection strings or environment values.

If a secret is accidentally committed, revoke it first, remove it from Git history using an approved incident process, and rotate any dependent credentials. Deleting only the working-tree file is insufficient.

## Threat boundaries

The local machine, database file, operating-system account, and container host are trusted. The application has no authentication or tenant isolation in this release and must not be exposed directly to untrusted networks. CORS defaults to local development origins.

API inputs are validated with Pydantic and bounded pagination. Sort columns are allowlisted. SQLAlchemy parameterization is used instead of string-built SQL. Database uniqueness, check, foreign-key, and cascade constraints enforce invariants after application validation.

## File-upload safety

Sprint 1 has no upload endpoint. Future uploads must use size and type allowlists, generated filenames, a non-public quarantine directory, malware inspection where appropriate, and must never execute uploaded content.

## Known limitations

- No authentication, authorization, rate limiting, or CSRF controls.
- SQLite is appropriate for local development, not an exposed multi-user service.
- Dependency and container-image vulnerability scans are not yet automated.
- Audit events record application mutations but are not cryptographically tamper-evident.
- Frontend content security policy and production reverse-proxy hardening remain deployment responsibilities.

## Reporting

Do not open a public issue containing secrets or exploit details. Contact the repository owner privately with affected version, reproduction steps, and impact. Do not include real brokerage credentials in any report.
