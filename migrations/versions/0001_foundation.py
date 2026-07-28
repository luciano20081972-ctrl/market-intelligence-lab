"""Create the Market Intelligence Lab foundation schema.

Revision ID: 0001_foundation
Revises: None
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("exchange", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("sector", sa.String(length=100), nullable=True),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assets")),
    )
    op.create_index(op.f("ix_assets_asset_type"), "assets", ["asset_type"])
    op.create_index(op.f("ix_assets_is_active"), "assets", ["is_active"])
    op.create_index(op.f("ix_assets_symbol"), "assets", ["symbol"], unique=True)

    op.create_table(
        "data_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("provider_type", sa.String(length=50), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("health", sa.String(length=32), nullable=False),
        sa.Column("last_successful_retrieval", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_sources")),
        sa.UniqueConstraint("name", name=op.f("uq_data_sources_name")),
    )

    op.create_table(
        "watchlists",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_watchlists")),
        sa.UniqueConstraint("name", name=op.f("uq_watchlists_name")),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(op.f("ix_audit_events_action"), "audit_events", ["action"])
    op.create_index(op.f("ix_audit_events_entity_id"), "audit_events", ["entity_id"])
    op.create_index(op.f("ix_audit_events_entity_type"), "audit_events", ["entity_type"])
    op.create_index(op.f("ix_audit_events_occurred_at"), "audit_events", ["occurred_at"])

    op.create_table(
        "data_ingestion_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("data_source_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_processed", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], name=op.f("fk_data_ingestion_runs_data_source_id_data_sources"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_ingestion_runs")),
    )
    op.create_index(op.f("ix_data_ingestion_runs_data_source_id"), "data_ingestion_runs", ["data_source_id"])

    op.create_table(
        "price_bars",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publication_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieval_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("high", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("low", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("close", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("adjusted_close", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("data_source_id", sa.Uuid(), nullable=False),
        sa.Column("is_demonstration_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("high >= low", name=op.f("ck_price_bars_price_high_gte_low")),
        sa.CheckConstraint("volume >= 0", name=op.f("ck_price_bars_price_volume_nonnegative")),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], name=op.f("fk_price_bars_asset_id_assets"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], name=op.f("fk_price_bars_data_source_id_data_sources"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price_bars")),
        sa.UniqueConstraint("asset_id", "interval", "event_time", "data_source_id", name="uq_price_bar_asset_interval_event_source"),
    )
    op.create_index(op.f("ix_price_bars_asset_id"), "price_bars", ["asset_id"])
    op.create_index("ix_price_bars_asset_event", "price_bars", ["asset_id", "event_time"])
    op.create_index(op.f("ix_price_bars_data_source_id"), "price_bars", ["data_source_id"])
    op.create_index(op.f("ix_price_bars_event_time"), "price_bars", ["event_time"])
    op.create_index(op.f("ix_price_bars_is_demonstration_data"), "price_bars", ["is_demonstration_data"])

    op.create_table(
        "watchlist_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("watchlist_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], name=op.f("fk_watchlist_assets_asset_id_assets"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["watchlist_id"], ["watchlists.id"], name=op.f("fk_watchlist_assets_watchlist_id_watchlists"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_watchlist_assets")),
        sa.UniqueConstraint("watchlist_id", "asset_id", name="uq_watchlist_asset_pair"),
    )
    op.create_index(op.f("ix_watchlist_assets_asset_id"), "watchlist_assets", ["asset_id"])
    op.create_index(op.f("ix_watchlist_assets_watchlist_id"), "watchlist_assets", ["watchlist_id"])


def downgrade() -> None:
    op.drop_table("watchlist_assets")
    op.drop_table("price_bars")
    op.drop_table("data_ingestion_runs")
    op.drop_table("audit_events")
    op.drop_table("watchlists")
    op.drop_table("data_sources")
    op.drop_table("assets")
