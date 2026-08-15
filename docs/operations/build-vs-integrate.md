# Operations build-vs-integrate audit

v0.14 extends the existing PostgreSQL-backed imports, schedules, unique schedule runs, job
events, leases, worker registrations, provider health/quota state, ingestion checkpoints,
raw-object boundary, Sentry boundary, and authenticated workspace controls. It adds a generic
scheduled-task layer only for work that is not an import. PostgreSQL row locks with `SKIP LOCKED`
and unique occurrence keys prevent duplicate scheduling; no Redis, Celery, Kafka, Airflow,
Temporal, Kubernetes, or second primary database is introduced.

`codex/auth-owner-recovery` was inspected read-only. Its identity-subject lookup and explicit
owner-linking command were still useful and were reimplemented against current main. The branch's
stale Phase-5 model, removed v0.11-v0.13 capabilities, old migrations, and deployment changes were
not ported.
