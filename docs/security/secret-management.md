# Secret management

Secrets enter only through environment/deployment secret stores. `.env` is local and ignored; `.env.example` contains blank placeholders. Supabase service-role keys, provider keys, JWTs, passwords, authorization headers, cookies, database credentials, Sentry DSNs, and vendor tokens must not be committed, returned by APIs, or sent to telemetry.

Use least privilege, separate environments, rotation dates, owner inventory, redacted fingerprints only when diagnosis requires them, and immediate revocation after suspected exposure. Frontend builds may contain only documented public/publishable keys.
