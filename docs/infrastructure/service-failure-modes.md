# Service failure modes

Supabase Auth outage blocks new/refreshing sessions and fails closed; authenticated application data must never fall back to a guessed user. GitHub/Codecov failure blocks collaboration or hosted reporting, not local operation. Sentry/Better Stack failure removes optional telemetry only. Cloudflare failure may remove edge/Tunnel access; origin recovery follows deployment policy. Resend is deferred; Supabase-managed Auth email remains the current reset/verification path. Provider failure stops imports and preserves existing bars without claiming health.

Recommended Better Stack monitors, if activated: `/health/live` every minute; `/health/ready` and `/api/v1/operations/health` with authenticated probes; worker heartbeat age over two poll intervals; nonzero dead-letter depth; sustained queue growth; and provider degraded/unavailable transitions. Never embed credentials in a monitor URL.

Cloudflare guidance, not deployment: strict TLS, proxied DNS, bounded rate rules, basic DDoS controls, authenticated development Tunnel, and encrypted R2 archives with lifecycle rules. Templates must receive account/zone IDs and tokens only from deployment secrets.
