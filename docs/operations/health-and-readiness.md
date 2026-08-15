# Health and readiness

`/health/live` reports that the process is alive. `/health/ready` verifies required database and
schema compatibility in staging/production. `/health/dependencies` reports sanitized database,
required-storage, and optional-provider status. An optional provider outage degrades operations but
does not by itself make the web application unready. `/health/deployment` exposes only immutable
version, Git SHA, Alembic revision, build time, environment name, and frontend version.
