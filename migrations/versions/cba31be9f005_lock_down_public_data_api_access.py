"""Lock down direct Data API access to application-owned public objects.

Revision ID: cba31be9f005
Revises: 18cca98a50d5
Create Date: 2026-07-30

Application authorization remains in FastAPI. PostgreSQL RLS is enabled as
deny-by-default defense in depth for non-owner roles, but this revision does
not claim workspace-aware RLS policies. The backend/migration owner keeps its
normal owner access and is not granted to browser-facing roles.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cba31be9f005"
down_revision: str | None = "18cca98a50d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPLICATION_TABLES = (
    "asset_metadata_versions",
    "assets",
    "audit_events",
    "backtest_daily_snapshots",
    "backtest_reproducibility_manifests",
    "backtest_runs",
    "backtest_trades",
    "backtest_validation_reports",
    "corporate_actions",
    "data_ingestion_runs",
    "data_sources",
    "exchange_calendars",
    "import_batches",
    "import_errors",
    "import_jobs",
    "import_schedules",
    "job_events",
    "job_leases",
    "operational_metrics",
    "paper_fills",
    "paper_orders",
    "paper_portfolios",
    "paper_positions",
    "portfolio_snapshots",
    "price_bars",
    "provider_comparisons",
    "provider_credentials",
    "provider_health_snapshots",
    "provider_rate_limit_states",
    "provider_symbol_mappings",
    "providers",
    "reconciliation_issues",
    "reconciliation_runs",
    "risk_rules",
    "schedule_runs",
    "signal_factors",
    "signals",
    "strategies",
    "strategy_versions",
    "trading_sessions",
    "user_profiles",
    "watchlist_assets",
    "watchlists",
    "worker_instances",
    "workspace_invitations",
    "workspace_memberships",
    "workspaces",
)


def _postgresql_only() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _postgresql_only():
        return

    # RLS without policies denies direct access to non-owner roles even if a
    # future grant is accidentally introduced. Do not FORCE RLS: the backend
    # and Alembic transport intentionally operate as the table owner.
    for table_name in APPLICATION_TABLES:
        op.execute(sa.text(f'ALTER TABLE public."{table_name}" ENABLE ROW LEVEL SECURITY'))

    # PUBLIC exists on every PostgreSQL deployment. Browser-facing Supabase
    # roles are conditional so the same canonical chain runs on vanilla PG17 CI.
    op.execute(sa.text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
    op.execute(sa.text("REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC"))
    op.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC"
        )
    )
    op.execute(
        sa.text(
            """
            DO $mil$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM anon;
                    REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM anon;
                    REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM anon;
                    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon;
                    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon;
                    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM anon;
                END IF;
            END
            $mil$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            DO $mil$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM authenticated;
                    REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM authenticated;
                    REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM authenticated;
                    ALTER DEFAULT PRIVILEGES IN SCHEMA public
                        REVOKE ALL ON TABLES FROM authenticated;
                    ALTER DEFAULT PRIVILEGES IN SCHEMA public
                        REVOKE ALL ON SEQUENCES FROM authenticated;
                    ALTER DEFAULT PRIVILEGES IN SCHEMA public
                        REVOKE EXECUTE ON FUNCTIONS FROM authenticated;
                END IF;
            END
            $mil$;
            """
        )
    )


def downgrade() -> None:
    if not _postgresql_only():
        return

    # Privilege revocations are intentionally not guessed back into existence:
    # previous grants can differ by deployment. A rollback only removes the RLS
    # defense-in-depth flag; an operator must explicitly review any re-grant.
    for table_name in APPLICATION_TABLES:
        op.execute(sa.text(f'ALTER TABLE public."{table_name}" DISABLE ROW LEVEL SECURITY'))
