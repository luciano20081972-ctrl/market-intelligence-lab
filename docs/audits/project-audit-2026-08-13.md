# Market Intelligence Lab audit — 2026-08-13

## Verified baseline

| Surface | Evidence | Status |
| --- | --- | --- |
| Local and server Git | `integrate/phase5-usability-branding` at `4973fa5`, clean | Verified complete |
| GitHub main | `69618fc` / v0.9.0 | Deferred intentionally |
| Deployed application | API v0.11.0; web `mil-web:0.11.0-4973fa5` | Verified complete |
| Database | Home PostgreSQL at Alembic `3b2f6c7d8e90` | Verified complete |
| Authentication | Production runs `MIL_AUTH_MODE=disabled`; no Supabase browser config | Blocked |
| Owner identity | Correct Supabase project active; intended email exists, confirmed, email provider | Verified complete |
| Owner application linkage | One local profile/workspace/owner membership, not linked to Supabase subject | Partially implemented |
| Supabase application schema | Empty and only migrated through v0.5.1 | Obsolete or unnecessary for canonical data |
| Mobile/PWA checkpoint | No manifest, service worker, or referenced documentation found | Not started |
| Public exposure | Funnel `:8443` targets Market Intelligence Lab; private default HTTPS targets IAmGodTranslator | Implemented but unverified as intended policy |
| Phase 5 compute | API, worker, supervisor and compute UI deployed | Verified complete |

## Conversation-derived register

| Request or commitment | Source | Current evidence | Status | Required action |
| --- | --- | --- | --- | --- |
| Beginner navigation/dashboard and official branding | Usability task, 2026-08-09 to 2026-08-10 | Deployed commit `4973fa5` | Verified complete | Retain |
| Permanent owner sign-in | Authentication conversations, 2026-08-10 to 2026-08-13 | Auth disabled in deployment | Blocked | Link owner, configure Supabase mode, deploy and verify |
| iPhone PWA/mobile shell | Usability Improvement Plan, 2026-08-12 | Transient work not found | Not started | Reimplement after auth checkpoint |
| Canonical private/public URL | Private Web App Plan and server work | Two different HTTPS routes and public Funnel | Partially implemented | User must choose private-only or Funnel policy |
| v0.10 hypothesis factory | Git commits `b798f27`, `deb8195` | Present under deployed history | Verified complete | Do not redo |
| v0.11 research memory versus Phase 5 | Roadmap and Phase 5 commit `35f145d` disagree | Compute foundations exist; research-memory scope not evidenced | Partially implemented | Reconcile release scope after auth/mobile |
| v0.12 skeptic/scenarios | Complete-project audit request | No verified release implementation | Not started | Future bounded release |
| v0.13 calibration/portfolio risk | Complete-project audit request | No verified release implementation | Not started | Future bounded release |
| v0.14 private-beta hardening | Complete-project audit request | Some controls exist; complete acceptance evidence absent | Partially implemented | Future hardening release |

## Authentication failure boundaries

1. The production frontend has no Supabase URL or publishable key compiled into it.
2. The production API runs authentication-disabled mode.
3. The confirmed Supabase owner identity is not linked to the existing home-server profile.
4. Existing hydration catches application failures without preserving a user-facing category.
5. The sign-in button previously had no pending state and only a generic error.

The canonical application data must remain in home-server PostgreSQL. The empty Supabase public
schema must not replace it. Supabase supplies identity and JWKS only.

## Resource snapshot

One instantaneous sample showed `mil-worker` at about 27% CPU. Memory was approximately API
231 MiB, worker 160 MiB, supervisor 163 MiB, web 3 MiB, and PostgreSQL 241 MiB. This is not a
time-series benchmark; optimization requires repeated idle and active samples before changes.

## Security findings

- The public Funnel makes the research UI internet-reachable while application auth is disabled.
- `public.alembic_version` has RLS disabled in the unused Supabase staging schema. Do not enable
  RLS automatically because migration access requires an explicit policy/role decision.
- Caddy access logs include request metadata for both applications; authorization values were
  redacted during inspection.

## Safest next checkpoint

Review and deploy the owner-auth recovery branch only after:

1. Backing up home PostgreSQL and deployment configuration.
2. Running the owner provisioner in dry-run mode with exact existing identifiers.
3. Approving the single linkage mutation.
4. Supplying Supabase public/frontend and backend URL/audience configuration through existing
   secret/config mechanisms.
5. Rebuilding only API and web, then verifying the real HTTPS owner flow.
