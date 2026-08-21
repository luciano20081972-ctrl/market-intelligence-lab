"""real market foundation

Revision ID: f01500000001
Revises: a141c0de0001
Create Date: 2026-08-21
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from alembic import context, op
import sqlalchemy as sa

import packages.database.types


revision: str = "f01500000001"
down_revision: str | None = "a141c0de0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FOUNDATION_NAMESPACE = uuid.UUID("2a17dc2d-d2c1-42ff-b795-7480bc09e4f1")


def _timestamps() -> tuple[sa.Column[datetime], sa.Column[datetime]]:
    return (
        sa.Column("created_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "issuers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("canonical_name", sa.String(length=240), nullable=False),
        sa.Column("search_name", sa.String(length=240), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("provenance", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_issuers")),
    )
    op.create_index(op.f("ix_issuers_cik"), "issuers", ["cik"], unique=True)
    op.create_index(op.f("ix_issuers_search_name"), "issuers", ["search_name"], unique=False)

    op.create_table(
        "asset_listings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("issuer_id", sa.Uuid(), nullable=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("normalized_symbol", sa.String(length=32), nullable=False),
        sa.Column("security_name", sa.String(length=240), nullable=False),
        sa.Column("exchange_code", sa.String(length=32), nullable=False),
        sa.Column("mic", sa.String(length=8), nullable=True),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("listing_status", sa.String(length=24), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_test_issue", sa.Boolean(), nullable=False),
        sa.Column("is_etf", sa.Boolean(), nullable=False),
        sa.Column("eligibility_status", sa.String(length=32), nullable=False),
        sa.Column("exclusion_reason", sa.String(length=160), nullable=True),
        sa.Column("valid_from", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("valid_to", packages.database.types.UTCDateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_record_key", sa.String(length=160), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="ck_asset_listings_listing_valid_range"
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["assets.id"], name=op.f("fk_asset_listings_asset_id_assets"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["issuer_id"], ["issuers.id"], name=op.f("fk_asset_listings_issuer_id_issuers"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset_listings")),
        sa.UniqueConstraint(
            "exchange_code", "normalized_symbol", "valid_from", name="uq_listing_symbol_period"
        ),
    )
    for column in ("asset_id", "issuer_id", "symbol", "normalized_symbol", "exchange_code", "mic", "asset_type", "listing_status", "is_active", "is_test_issue", "is_etf", "eligibility_status", "valid_from", "valid_to"):
        op.create_index(op.f(f"ix_asset_listings_{column}"), "asset_listings", [column], unique=False)
    op.create_index(op.f("ix_asset_listings_source"), "asset_listings", ["source"])
    op.create_index(
        op.f("ix_asset_listings_source_record_key"),
        "asset_listings",
        ["source_record_key"],
    )
    op.create_index("ix_listing_active_search", "asset_listings", ["is_active", "normalized_symbol"])

    op.create_table(
        "asset_identifiers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("issuer_id", sa.Uuid(), nullable=True),
        sa.Column("identifier_type", sa.String(length=32), nullable=False),
        sa.Column("identifier_value", sa.String(length=160), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("valid_from", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("valid_to", packages.database.types.UTCDateTime(timezone=True), nullable=True),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_asset_identifiers_asset_identifier_valid_range",
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["issuer_id"], ["issuers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset_identifiers")),
        sa.UniqueConstraint(
            "asset_id", "identifier_type", "source", "valid_from", name="uq_asset_identifier_period"
        ),
    )
    for column in ("asset_id", "issuer_id", "identifier_type", "identifier_value", "source", "valid_from", "valid_to"):
        op.create_index(op.f(f"ix_asset_identifiers_{column}"), "asset_identifiers", [column])
    op.create_index(
        "ix_asset_identifier_lookup", "asset_identifiers", ["identifier_type", "identifier_value"]
    )

    op.create_table(
        "reference_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_record_key", sa.String(length=160), nullable=False),
        sa.Column("retrieval_time", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("source_version", sa.String(length=120), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("raw_object_reference", sa.String(length=700), nullable=True),
        sa.Column("media_type", sa.String(length=120), nullable=False),
        sa.Column("reconciliation_outcome", sa.String(length=32), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=True),
        sa.Column("issuer_id", sa.Uuid(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["issuer_id"], ["issuers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reference_observations")),
        sa.UniqueConstraint("source", "checksum", name="uq_reference_observation_checksum"),
    )
    for column in ("source", "source_record_key", "retrieval_time", "checksum", "reconciliation_outcome", "asset_id", "issuer_id"):
        op.create_index(op.f(f"ix_reference_observations_{column}"), "reference_observations", [column])

    op.create_table(
        "asset_capabilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("capability", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column("feed_type", sa.String(length=24), nullable=False),
        sa.Column("as_of_time", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("valid_until", packages.database.types.UTCDateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=240), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("updated_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset_capabilities")),
        sa.UniqueConstraint("asset_id", "capability", "provider_code", name="uq_asset_capability_provider"),
    )
    for column in ("asset_id", "capability", "status", "provider_code", "feed_type", "as_of_time", "valid_until"):
        op.create_index(op.f(f"ix_asset_capabilities_{column}"), "asset_capabilities", [column])
    op.create_index("ix_asset_capability_status", "asset_capabilities", ["capability", "status"])

    op.create_table(
        "provider_asset_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("provider_symbol", sa.String(length=64), nullable=False),
        sa.Column("exchange_code", sa.String(length=32), nullable=False),
        sa.Column("valid_from", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("valid_to", packages.database.types.UTCDateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="ck_provider_asset_mappings_provider_asset_mapping_valid_range"
        ),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_asset_mappings")),
        sa.UniqueConstraint("provider_id", "asset_id", "valid_from", name="uq_provider_asset_mapping_period"),
        sa.UniqueConstraint("provider_id", "provider_symbol", "valid_from", name="uq_provider_symbol_period"),
    )
    for column in ("provider_id", "asset_id", "provider_symbol", "valid_from", "valid_to", "is_active"):
        op.create_index(op.f(f"ix_provider_asset_mappings_{column}"), "provider_asset_mappings", [column])
    op.create_index("ix_provider_asset_mapping_current", "provider_asset_mappings", ["provider_id", "asset_id", "valid_to"])

    op.create_table(
        "universe_selection_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("effective_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("provider_code", sa.String(length=64), nullable=True),
        sa.Column("realtime_capacity", sa.Integer(), nullable=False),
        sa.Column("input_asset_count", sa.Integer(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("active_count", sa.Integer(), nullable=False),
        sa.Column("realtime_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("created_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_universe_selection_runs")),
    )
    for column in ("workspace_id", "effective_at", "policy_version", "status"):
        op.create_index(op.f(f"ix_universe_selection_runs_{column}"), "universe_selection_runs", [column])
    op.create_index(
        op.f("ix_universe_selection_runs_checksum"),
        "universe_selection_runs",
        ["checksum"],
        unique=True,
    )

    op.create_table(
        "universe_layer_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("selection_run_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("layer", sa.String(length=32), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("score", sa.Numeric(18, 8), nullable=True),
        sa.Column("score_components", sa.JSON(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("effective_from", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("effective_to", packages.database.types.UTCDateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["selection_run_id"], ["universe_selection_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_universe_layer_memberships")),
        sa.UniqueConstraint("selection_run_id", "layer", "asset_id", name="uq_universe_layer_run_asset"),
    )
    for column in ("selection_run_id", "workspace_id", "asset_id", "layer", "effective_from", "effective_to"):
        op.create_index(op.f(f"ix_universe_layer_memberships_{column}"), "universe_layer_memberships", [column])
    op.create_index("ix_universe_layer_current", "universe_layer_memberships", ["workspace_id", "layer", "effective_to"])

    op.create_table(
        "market_operating_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("calendar_code", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=24), nullable=False),
        sa.Column("effective_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("session_date", sa.String(length=10), nullable=True),
        sa.Column("market_open", packages.database.types.UTCDateTime(timezone=True), nullable=True),
        sa.Column("market_close", packages.database.types.UTCDateTime(timezone=True), nullable=True),
        sa.Column("next_transition_at", packages.database.types.UTCDateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=240), nullable=False),
        sa.Column("scheduler_state", sa.JSON(), nullable=False),
        sa.Column("created_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_operating_states")),
    )
    for column in ("calendar_code", "mode", "effective_at", "session_date", "next_transition_at"):
        op.create_index(op.f(f"ix_market_operating_states_{column}"), "market_operating_states", [column])

    op.add_column("import_jobs", sa.Column("priority", sa.Integer(), server_default="100", nullable=False))
    op.add_column("import_jobs", sa.Column("resource_class", sa.String(length=32), server_default="IO_STANDARD", nullable=False))
    op.add_column("import_jobs", sa.Column("queue_wait_ms", sa.Integer(), server_default="0", nullable=False))
    op.add_column("import_jobs", sa.Column("peak_memory_mb", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_import_jobs_priority"), "import_jobs", ["priority"])
    op.create_index(op.f("ix_import_jobs_resource_class"), "import_jobs", ["resource_class"])

    _backfill_existing_assets()


def _backfill_existing_assets() -> None:
    if context.is_offline_mode():
        # Offline SQL cannot inspect and deterministically reconcile existing
        # identity rows. The same migration performs the additive backfill on
        # every real online upgrade.
        return
    connection = op.get_bind()
    now = datetime(2026, 8, 21, tzinfo=UTC)
    assets = connection.execute(
        sa.text("SELECT id, symbol, name, asset_type, exchange, is_active, created_at FROM assets")
    ).mappings()
    listing_table = sa.table(
        "asset_listings",
        sa.column("id", sa.Uuid()), sa.column("asset_id", sa.Uuid()), sa.column("issuer_id", sa.Uuid()),
        sa.column("symbol", sa.String()), sa.column("normalized_symbol", sa.String()),
        sa.column("security_name", sa.String()), sa.column("exchange_code", sa.String()),
        sa.column("mic", sa.String()), sa.column("asset_type", sa.String()),
        sa.column("listing_status", sa.String()), sa.column("is_active", sa.Boolean()),
        sa.column("is_test_issue", sa.Boolean()), sa.column("is_etf", sa.Boolean()),
        sa.column("eligibility_status", sa.String()), sa.column("exclusion_reason", sa.String()),
        sa.column("valid_from", packages.database.types.UTCDateTime()),
        sa.column("valid_to", packages.database.types.UTCDateTime()), sa.column("source", sa.String()),
        sa.column("source_record_key", sa.String()), sa.column("provenance", sa.JSON()),
        sa.column("created_at", packages.database.types.UTCDateTime()),
        sa.column("updated_at", packages.database.types.UTCDateTime()),
    )
    capability_table = sa.table(
        "asset_capabilities",
        sa.column("id", sa.Uuid()), sa.column("asset_id", sa.Uuid()),
        sa.column("capability", sa.String()), sa.column("status", sa.String()),
        sa.column("provider_code", sa.String()), sa.column("feed_type", sa.String()),
        sa.column("as_of_time", packages.database.types.UTCDateTime()),
        sa.column("valid_until", packages.database.types.UTCDateTime()), sa.column("reason", sa.String()),
        sa.column("details", sa.JSON()), sa.column("updated_at", packages.database.types.UTCDateTime()),
    )
    for asset in assets:
        raw_asset_id = asset["id"]
        asset_id = uuid.UUID(str(raw_asset_id))
        symbol = str(asset["symbol"]).upper()
        created = asset["created_at"] or now
        if isinstance(created, str):
            created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        connection.execute(
            listing_table.insert().values(
                id=uuid.uuid5(FOUNDATION_NAMESPACE, f"legacy-listing:{asset_id}"), asset_id=asset_id,
                issuer_id=None, symbol=symbol, normalized_symbol=symbol, security_name=asset["name"],
                exchange_code=asset["exchange"] or "UNKNOWN", mic=None, asset_type=asset["asset_type"],
                listing_status="ACTIVE" if asset["is_active"] else "INACTIVE",
                is_active=bool(asset["is_active"]), is_test_issue=False,
                is_etf=str(asset["asset_type"]).lower() == "etf", eligibility_status="ELIGIBLE",
                exclusion_reason=None, valid_from=created, valid_to=None, source="legacy_asset",
                source_record_key=f"legacy:{asset_id}", provenance={"migration":"f01500000001"},
                created_at=now, updated_at=now,
            )
        )
        bar_count = connection.scalar(
            sa.text("SELECT count(*) FROM price_bars WHERE asset_id=:asset_id"),
            {"asset_id": raw_asset_id},
        )
        rows = [
            ("REFERENCE", "REFERENCE_AVAILABLE", "aggregate", "UNAVAILABLE", "Preserved v0.14.1 asset"),
            (
                "HISTORICAL", "HISTORICAL_AVAILABLE" if bar_count else "INSUFFICIENT_DATA",
                "synthetic" if bar_count else "aggregate", "DEMO" if bar_count else "UNAVAILABLE",
                "Existing bars are explicitly classified as demonstration data" if bar_count else "No stored bars",
            ),
        ]
        for capability, status, provider_code, feed_type, reason in rows:
            connection.execute(
                capability_table.insert().values(
                    id=uuid.uuid5(FOUNDATION_NAMESPACE, f"legacy-capability:{asset_id}:{capability}"),
                    asset_id=asset_id, capability=capability, status=status,
                    provider_code=provider_code, feed_type=feed_type, as_of_time=now,
                    valid_until=None, reason=reason, details={"migration":"f01500000001"}, updated_at=now,
                )
            )


def downgrade() -> None:
    op.drop_index(op.f("ix_import_jobs_resource_class"), table_name="import_jobs")
    op.drop_index(op.f("ix_import_jobs_priority"), table_name="import_jobs")
    op.drop_column("import_jobs", "peak_memory_mb")
    op.drop_column("import_jobs", "queue_wait_ms")
    op.drop_column("import_jobs", "resource_class")
    op.drop_column("import_jobs", "priority")
    for table in (
        "market_operating_states",
        "universe_layer_memberships",
        "universe_selection_runs",
        "provider_asset_mappings",
        "asset_capabilities",
        "reference_observations",
        "asset_identifiers",
        "asset_listings",
        "issuers",
    ):
        op.drop_table(table)
