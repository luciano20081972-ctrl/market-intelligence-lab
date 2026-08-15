# Production configuration

Production fails closed when authentication is disabled, CORS or trusted hosts contain wildcards,
PostgreSQL is absent, required Supabase identity configuration is absent, or raw-object storage is
explicitly temporary. Secrets stay in the deployment's secure environment path and are never
returned by APIs or readiness output. Development and isolated E2E modes must be explicit.
