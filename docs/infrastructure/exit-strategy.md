# Infrastructure exit strategy

- GitHub: mirror Git, export releases/issues, and retain CI definitions; alternatives include GitLab or Forgejo.
- Supabase: export PostgreSQL and Auth identities through supported administration paths; replace with PostgreSQL plus an OIDC provider.
- Cloudflare: export DNS and R2 objects; replace DNS/CDN/tunnel/storage independently.
- Sentry: retain structured application logs and OpenTelemetry-compatible boundaries.
- Better Stack: health endpoints are vendor-neutral and can move to Uptime Kuma or Grafana.
- Codecov: XML/LCOV artifacts and local thresholds remain authoritative.
- Resend: templates stay in source and can move to another transactional mail provider.

Exercise exports before a critical service becomes active, document recovery time/data-loss expectations, and never make a free tier the only copy of irreplaceable data.
