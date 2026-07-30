# Workspace isolation

Canonical assets, bars, calendars, corporate actions, and provider definitions are shared. Watchlists, strategies/versions through their parent, backtests/results, paper portfolios/orders/fills/risk rules through their parent, import jobs, user schedules, comparisons, and audits are workspace-owned.

All API sessions receive verified user/workspace context. SQLAlchemy loader criteria scope owned reads, the flush guard assigns and rejects conflicting workspace IDs, composite unique constraints include workspace, and background schedule execution copies the schedule workspace to its job. Tests cover cross-workspace list/read denial and viewer mutation denial.

PostgreSQL RLS is not enabled in v0.5.0. Partial policies would create false assurance because workers and direct application connections require a complete transaction-local identity design. Strict application-layer isolation is implemented and tested; complete RLS, service-account policies, `SET LOCAL` context, and pooled-context tests are required before v1.0.
