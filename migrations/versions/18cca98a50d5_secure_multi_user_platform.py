"""Secure multi-user and production foundation.

Revision ID: 18cca98a50d5
Revises: 1a52c2d25013
Create Date: 2026-07-29
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import op

from packages.database.types import UTCDateTime

revision: str = "18cca98a50d5"
down_revision: str | None = "1a52c2d25013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
LEGACY_WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000002")


def _add_workspace_scope(
    table_name: str,
    *,
    old_unique: str | None = None,
    new_unique: tuple[str, list[str]] | None = None,
) -> None:
    bind = op.get_bind()
    stored_id = (
        LEGACY_WORKSPACE_ID.hex if bind.dialect.name == "sqlite" else str(LEGACY_WORKSPACE_ID)
    )
    with op.batch_alter_table(table_name) as batch:
        batch.add_column(
            sa.Column(
                "workspace_id",
                sa.Uuid(),
                nullable=True,
                server_default=sa.text(f"'{stored_id}'"),
            )
        )
    op.execute(
        sa.text(f"UPDATE {table_name} SET workspace_id = :workspace_id").bindparams(
            sa.bindparam("workspace_id", value=LEGACY_WORKSPACE_ID, type_=sa.Uuid())
        )
    )
    with op.batch_alter_table(table_name) as batch:
        if old_unique:
            batch.drop_constraint(old_unique, type_="unique")
        batch.alter_column("workspace_id", nullable=False, server_default=None)
        batch.create_index(f"ix_{table_name}_workspace_id", ["workspace_id"])
        batch.create_foreign_key(
            f"fk_{table_name}_workspace_id_workspaces",
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="CASCADE",
        )
        if new_unique:
            batch.create_unique_constraint(new_unique[0], new_unique[1])


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("auth_subject", sa.String(160), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("is_disabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
    )
    op.create_index("ix_user_profiles_auth_subject", "user_profiles", ["auth_subject"], unique=True)
    op.create_index("ix_user_profiles_email", "user_profiles", ["email"])
    op.create_index("ix_user_profiles_is_disabled", "user_profiles", ["is_disabled"])
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user_profiles.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_workspaces_created_by_user_id", "workspaces", ["created_by_user_id"])
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"], unique=True)
    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.CheckConstraint("role IN ('owner','admin','member','viewer')", name="membership_role"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership_user"),
    )
    op.create_index(
        "ix_workspace_memberships_workspace_id", "workspace_memberships", ["workspace_id"]
    )
    op.create_index("ix_workspace_memberships_user_id", "workspace_memberships", ["user_id"])
    op.create_index("ix_workspace_memberships_role", "workspace_memberships", ["role"])
    now = datetime(2025, 1, 1, tzinfo=UTC)
    user_table = sa.table(
        "user_profiles",
        sa.column("id", sa.Uuid()),
        sa.column("auth_subject", sa.String()),
        sa.column("email", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("email_verified", sa.Boolean()),
        sa.column("is_disabled", sa.Boolean()),
        sa.column("created_at", UTCDateTime()),
        sa.column("updated_at", UTCDateTime()),
    )
    workspace_table = sa.table(
        "workspaces",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("slug", sa.String()),
        sa.column("created_by_user_id", sa.Uuid()),
        sa.column("created_at", UTCDateTime()),
        sa.column("updated_at", UTCDateTime()),
    )
    membership_table = sa.table(
        "workspace_memberships",
        sa.column("id", sa.Uuid()),
        sa.column("workspace_id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("role", sa.String()),
        sa.column("created_at", UTCDateTime()),
        sa.column("updated_at", UTCDateTime()),
    )
    op.bulk_insert(
        user_table,
        [
            {
                "id": LEGACY_USER_ID,
                "auth_subject": "development-user",
                "email": "developer@localhost.invalid",
                "display_name": "Local Developer",
                "email_verified": True,
                "is_disabled": False,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    op.bulk_insert(
        workspace_table,
        [
            {
                "id": LEGACY_WORKSPACE_ID,
                "name": "Legacy Development Workspace",
                "slug": "legacy-development",
                "created_by_user_id": LEGACY_USER_ID,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    op.bulk_insert(
        membership_table,
        [
            {
                "id": uuid4(),
                "workspace_id": LEGACY_WORKSPACE_ID,
                "user_id": LEGACY_USER_ID,
                "role": "owner",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )

    _add_workspace_scope(
        "watchlists",
        old_unique="uq_watchlists_name",
        new_unique=("uq_watchlist_workspace_name", ["workspace_id", "name"]),
    )
    _add_workspace_scope(
        "strategies",
        old_unique="uq_strategies_name",
        new_unique=("uq_strategy_workspace_name", ["workspace_id", "name"]),
    )
    _add_workspace_scope("backtest_runs")
    _add_workspace_scope(
        "paper_portfolios",
        old_unique="uq_paper_portfolios_name",
        new_unique=("uq_portfolio_workspace_name", ["workspace_id", "name"]),
    )
    _add_workspace_scope("import_jobs")
    with op.batch_alter_table("import_jobs") as batch:
        batch.drop_index("ix_import_jobs_idempotency_key")
        batch.create_index("ix_import_jobs_idempotency_key", ["idempotency_key"])
        batch.create_unique_constraint(
            "uq_import_job_workspace_key", ["workspace_id", "idempotency_key"]
        )
    _add_workspace_scope(
        "import_schedules",
        old_unique="uq_import_schedule_provider_name",
        new_unique=(
            "uq_import_schedule_workspace_provider_name",
            ["workspace_id", "provider_id", "name"],
        ),
    )

    with op.batch_alter_table("audit_events") as batch:
        batch.add_column(sa.Column("actor_user_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("workspace_id", sa.Uuid(), nullable=True))
        batch.add_column(
            sa.Column("result", sa.String(24), nullable=False, server_default="success")
        )
        batch.add_column(sa.Column("correlation_id", sa.String(80), nullable=True))
        batch.add_column(sa.Column("ip_metadata", sa.String(80), nullable=True))
        batch.add_column(sa.Column("user_agent_summary", sa.String(160), nullable=True))
        batch.create_index("ix_audit_events_actor_user_id", ["actor_user_id"])
        batch.create_index("ix_audit_events_workspace_id", ["workspace_id"])
        batch.create_index("ix_audit_events_correlation_id", ["correlation_id"])
        batch.create_foreign_key(
            "fk_audit_events_actor_user_id_user_profiles",
            "user_profiles",
            ["actor_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_audit_events_workspace_id_workspaces",
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.execute(
        sa.text(
            "UPDATE audit_events SET actor_user_id=:user_id, workspace_id=:workspace_id "
            "WHERE actor_user_id IS NULL"
        ).bindparams(
            sa.bindparam("user_id", value=LEGACY_USER_ID, type_=sa.Uuid()),
            sa.bindparam("workspace_id", value=LEGACY_WORKSPACE_ID, type_=sa.Uuid()),
        )
    )

    op.create_table(
        "workspace_invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("email", sa.String(320), nullable=False, index=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(24), nullable=False, index=True),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("expires_at", UTCDateTime(), nullable=False, index=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.CheckConstraint("role IN ('admin','member','viewer')", name="invitation_role"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["user_profiles.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "provider_comparisons",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("asset_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("primary_provider_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("secondary_provider_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("start_time", UTCDateTime(), nullable=False),
        sa.Column("end_time", UTCDateTime(), nullable=False),
        sa.Column("tolerance_configuration", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("disagreements", sa.JSON(), nullable=False),
        sa.Column("resolution_status", sa.String(32), nullable=False, index=True),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("resolved_by_user_id", sa.Uuid(), nullable=True, index=True),
        sa.Column("compared_at", UTCDateTime(), nullable=False, index=True),
        sa.Column("resolved_at", UTCDateTime(), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["primary_provider_id"], ["providers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["secondary_provider_id"], ["providers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["user_profiles.id"], ondelete="SET NULL"),
    )
    op.create_table(
        "backtest_reproducibility_manifests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("backtest_run_id", sa.Uuid(), nullable=False, unique=True, index=True),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("manifest_checksum", sa.String(64), nullable=False, index=True),
        sa.Column("generated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["backtest_run_id"], ["backtest_runs.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "backtest_validation_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("backtest_run_id", sa.Uuid(), nullable=False, unique=True, index=True),
        sa.Column("overall_status", sa.String(24), nullable=False, index=True),
        sa.Column("is_validated", sa.Boolean(), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("generated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["backtest_run_id"], ["backtest_runs.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("backtest_validation_reports")
    op.drop_table("backtest_reproducibility_manifests")
    op.drop_table("provider_comparisons")
    op.drop_table("workspace_invitations")
    with op.batch_alter_table("audit_events") as batch:
        batch.drop_column("user_agent_summary")
        batch.drop_column("ip_metadata")
        batch.drop_column("correlation_id")
        batch.drop_column("result")
        batch.drop_column("workspace_id")
        batch.drop_column("actor_user_id")
    scope_tables = (
        "import_schedules",
        "import_jobs",
        "paper_portfolios",
        "backtest_runs",
        "strategies",
        "watchlists",
    )
    for table_name in scope_tables:
        with op.batch_alter_table(table_name) as batch:
            batch.drop_column("workspace_id")
    op.drop_table("workspace_memberships")
    op.drop_table("workspaces")
    op.drop_table("user_profiles")
