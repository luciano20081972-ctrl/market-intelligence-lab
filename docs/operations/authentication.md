# Authentication operations

The browser receives only the Supabase URL and publishable key. Server secret keys never enter the
bundle and are not end-user JWTs. The API verifies JWKS signatures, issuer, audience, expiry, and
subject, then resolves the subject to an existing application profile and workspace membership.
Password recovery redirects to the current origin's `/reset-password` path.

Owner recovery uses `python -m scripts.provision_owner` in dry-run mode by default. It requires an
existing profile, workspace, owner membership, and legitimate Supabase subject; it creates none of
those records and records one immutable audit event when a real change is applied.
