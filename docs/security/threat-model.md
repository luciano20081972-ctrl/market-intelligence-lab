# Threat model

Protected assets include identities, workspace research, simulated orders, provider keys, licensed data, audit history, backups, and software supply chain.

| Threat | Principal controls | Residual work |
|---|---|---|
| Stolen/expired token | short-lived provider sessions, signature/claim checks, 401, no token logging | provider/session revocation latency |
| Cross-workspace access / IDOR | membership policy, loader criteria, composite uniqueness, uniform 404, negative tests | PostgreSQL RLS before v1.0 |
| Compromised API key | environment-only key, header auth, redaction, fixed host | managed secret rotation |
| Provider response injection / malicious CSV | response-size/type/schema/value checks, no raw error body | fuzz corpus expansion |
| Worker impersonation | durable registered worker IDs, leases, explicit job workspace | service-account identity for distributed workers |
| Audit tampering | insert-only service and read-only API | database append-only grants/WORM export |
| Replay / duplicate simulated order | scoped idempotency keys and unique constraints | distributed replay window metrics |
| Dependency compromise | locked npm tree, Dependabot, audits, SBOM/licenses, pinned CI actions | signed provenance/attestation |
| Exposed backups | no repository backups, encryption/access/lifecycle guidance | deployed restore drill |
| Bias/data leakage | deterministic rule report blocks validated status on critical failure | point-in-time universe/revision datasets |

No brokerage, real-money, margin, short, options, withdrawal, or autonomous execution boundary exists.
