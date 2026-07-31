# Workspace isolation

Canonical assets, bars, calendars, corporate actions, and provider definitions are shared. Watchlists, strategies/versions through their parent, backtests/results, paper portfolios/orders/fills/risk rules through their parent, import jobs, user schedules, comparisons, and audits are workspace-owned.

All API sessions receive verified user/workspace context. SQLAlchemy loader criteria scope owned reads, the flush guard assigns and rejects conflicting workspace IDs, composite unique constraints include workspace, and background schedule execution copies the schedule workspace to its job. Tests cover cross-workspace list/read denial and viewer mutation denial.

Revision `cba31be9f005` enables RLS on every application table but creates no direct browser-facing policies. Together with revoked `anon` and `authenticated` privileges, this is deny-by-default PostgREST defense in depth. It is not workspace-aware RLS: FastAPI and Alembic use the table-owning backend role, which retains owner access and normally bypasses RLS.

Strict application-layer isolation remains the authorization boundary and is tested on SQLite and disposable PostgreSQL 17. Complete database-enforced workspace policies would require transaction-local verified identity, service/worker policies, `SET LOCAL` context, policy indexes, and pooled-context leakage tests before they could replace or supplement this boundary.

The bounded v0.5.1 staging rehearsal used two live Supabase identities with two
temporary local application workspaces and different roles. It verified
cross-workspace read/write and guessed-ID denial, viewer mutation denial, owner
membership control, and redacted audit creation. This proves the application
authorization paths with live provider identities; PostgreSQL 17 workspace
guards and transaction behavior remain a separate GitHub Actions gate.
