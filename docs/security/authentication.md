# Authentication

`MIL_AUTH_MODE=disabled|supabase`. Disabled mode creates a deterministic local owner and is accepted only in development/test; production settings reject it. Supabase mode requires `MIL_SUPABASE_URL`; FastAPI accepts only Bearer tokens verified against the project's asymmetric JWKS with issuer, audience, expiry, issued-at, and subject checks. JWKS keys cache for five minutes and refresh on rotation/key miss.

The React client uses the supported Supabase client for sign-in, sign-out, session restoration, refresh, reset request, and reset completion. `VITE_SUPABASE_PUBLISHABLE_KEY` is public configuration. A service-role key is neither required nor permitted in frontend configuration. Passwords and tokens are never stored by application models or logged.

Disabled users receive 401. Missing, expired, wrong-issuer/audience, and invalid-signature tokens fail closed. Supabase session revocation is honored when the provider rejects refresh/access; application-level immediate revocation beyond provider support is deferred.
