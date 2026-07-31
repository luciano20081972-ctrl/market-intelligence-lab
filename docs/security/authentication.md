# Authentication

`MIL_AUTH_MODE=disabled|supabase`. Disabled mode creates a deterministic local owner and is accepted only in development/test; production settings reject it. Supabase mode requires `MIL_SUPABASE_URL`; FastAPI accepts only Bearer tokens verified against the project's asymmetric JWKS with issuer, audience, expiry, issued-at, and subject checks. JWKS keys cache for five minutes and refresh on rotation/key miss.

The React client uses the supported Supabase client for sign-in, sign-out, session restoration, refresh, reset request, and reset completion. `VITE_SUPABASE_PUBLISHABLE_KEY` is public configuration. A service-role key is neither required nor permitted in frontend configuration. Passwords and tokens are never stored by application models or logged.

`MIL_SUPABASE_SECRET_KEY` is backend-only validation/administration configuration and must never use a `VITE_` prefix or enter a frontend build. Live staging tests create temporary identities, keep tokens and passwords in memory, revoke/sign out sessions before deletion where supported, and report only pass/fail classifications.

Disabled users receive 401. Missing, expired, wrong-issuer/audience, and invalid-signature tokens fail closed. Supabase session revocation is honored when the provider rejects refresh/access; application-level immediate revocation beyond provider support is deferred.

The v0.5.1 staging rehearsal live-verified password sign-in, asymmetric JWT
signature, issuer, audience, expiry, subject, refresh, sign-out, and rejected
post-logout refresh. The same live tokens passed `/api/v1/auth/me` and
`/api/v1/users/me` against a temporary local application database. The direct
FastAPI-to-staging PostgreSQL runtime path remains unverified because the
workstation's session-pooler authentication is unresolved.
