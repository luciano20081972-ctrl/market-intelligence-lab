"""hybrid compute and always-on market supervisor

Revision ID: 3b2f6c7d8e90
Revises: ed23735efb90
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import packages.database.types


revision: str = "3b2f6c7d8e90"
down_revision: str | None = "ed23735efb90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "compute_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("submission_key", sa.String(160), nullable=False),
        sa.Column("job_type", sa.String(80), nullable=False),
        sa.Column("job_class", sa.String(32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("deadline", packages.database.types.UTCDateTime(timezone=True), nullable=True),
        sa.Column("symbols", sa.JSON(), nullable=False),
        sa.Column("date_start", sa.Date(), nullable=True),
        sa.Column("date_end", sa.Date(), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("strategy_version", sa.String(160), nullable=True),
        sa.Column("hypothesis_version", sa.String(160), nullable=True),
        sa.Column("model_version", sa.String(160), nullable=True),
        sa.Column("input_manifest", sa.JSON(), nullable=False),
        sa.Column("input_manifest_hash", sa.String(64), nullable=False),
        sa.Column("data_provenance", sa.JSON(), nullable=False),
        sa.Column("data_version", sa.String(160), nullable=True),
        sa.Column("estimated_cpu", sa.Numeric(8, 3), nullable=False),
        sa.Column("estimated_ram_mb", sa.Integer(), nullable=False),
        sa.Column("estimated_runtime_seconds", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("max_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("selected_provider", sa.String(48), nullable=True),
        sa.Column("cloud_execution_id", sa.String(320), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("checkpoint_state", sa.JSON(), nullable=False),
        sa.Column("result_manifest", sa.JSON(), nullable=False),
        sa.Column("error_classification", sa.String(48), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("started_at", packages.database.types.UTCDateTime(timezone=True), nullable=True),
        sa.Column("completed_at", packages.database.types.UTCDateTime(timezone=True), nullable=True),
        sa.Column("updated_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "job_class IN ('INTERACTIVE_LIGHT','STANDARD','HEAVY','VERY_HEAVY')",
            name="compute_job_class_valid",
        ),
        sa.CheckConstraint(
            "state IN ('QUEUED','ESTIMATING','ROUTING','LOCAL_RUNNING','CLOUD_SUBMITTING','CLOUD_QUEUED','CLOUD_RUNNING','CHECKPOINTED','RESULT_VALIDATING','SUCCEEDED','FAILED_RETRYABLE','FAILED_FINAL','CANCELED','BLOCKED_BY_BUDGET','WAITING_FOR_CAPACITY','CLOUD_DISABLED')",
            name="compute_job_state_valid",
        ),
        sa.CheckConstraint("priority >= 0 AND priority <= 100", name="compute_job_priority_valid"),
        sa.CheckConstraint("attempt_count >= 0", name="compute_job_attempt_nonnegative"),
        sa.CheckConstraint(
            "max_attempts >= 1 AND max_attempts <= 10", name="compute_job_max_attempts_valid"
        ),
        sa.CheckConstraint("estimated_cpu > 0", name="compute_job_cpu_positive"),
        sa.CheckConstraint("estimated_ram_mb > 0", name="compute_job_ram_positive"),
        sa.CheckConstraint(
            "estimated_runtime_seconds > 0", name="compute_job_runtime_positive"
        ),
        sa.CheckConstraint("estimated_cost_usd >= 0", name="compute_job_cost_nonnegative"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["user_profiles.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "submission_key", name="uq_compute_job_submission"),
        sa.UniqueConstraint("cloud_execution_id"),
    )
    for column in (
        "workspace_id",
        "requested_by_user_id",
        "job_type",
        "job_class",
        "state",
        "deadline",
        "input_manifest_hash",
        "selected_provider",
        "created_at",
    ):
        op.create_index(op.f(f"ix_compute_jobs_{column}"), "compute_jobs", [column])
    op.create_index(
        "ix_compute_job_workspace_state_priority",
        "compute_jobs",
        ["workspace_id", "state", "priority"],
    )

    op.create_table(
        "compute_job_transitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("from_state", sa.String(32), nullable=True),
        sa.Column("to_state", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["compute_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_compute_job_transitions_job_id"), "compute_job_transitions", ["job_id"])
    op.create_index(op.f("ix_compute_job_transitions_to_state"), "compute_job_transitions", ["to_state"])
    op.create_index(op.f("ix_compute_job_transitions_created_at"), "compute_job_transitions", ["created_at"])
    op.create_index(
        "ix_compute_transition_job_created", "compute_job_transitions", ["job_id", "created_at"]
    )

    op.create_table(
        "cloud_usage_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(48), nullable=False),
        sa.Column("estimated_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("observed_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("task_count", sa.Integer(), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("created_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.CheckConstraint("estimated_usd >= 0", name="cloud_usage_estimate_nonnegative"),
        sa.CheckConstraint("observed_usd IS NULL OR observed_usd >= 0", name="cloud_usage_observed_nonnegative"),
        sa.CheckConstraint("task_count >= 1", name="cloud_usage_task_count_positive"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["compute_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("workspace_id", "job_id", "provider", "usage_date"):
        op.create_index(op.f(f"ix_cloud_usage_ledger_{column}"), "cloud_usage_ledger", [column])
    op.create_index(
        "ix_cloud_usage_workspace_date", "cloud_usage_ledger", ["workspace_id", "usage_date"]
    )

    op.create_table(
        "market_supervisor_heartbeats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("instance_id", sa.String(160), nullable=False),
        sa.Column("session_state", sa.String(24), nullable=False),
        sa.Column("cloud_enabled", sa.Boolean(), nullable=False),
        sa.Column("provider_health", sa.JSON(), nullable=False),
        sa.Column("scheduler_state", sa.JSON(), nullable=False),
        sa.Column("last_signal_scan_at", packages.database.types.UTCDateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("heartbeat_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("started_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_market_supervisor_heartbeats_instance_id"),
        "market_supervisor_heartbeats",
        ["instance_id"],
        unique=True,
    )
    for column in ("session_state", "heartbeat_at"):
        op.create_index(
            op.f(f"ix_market_supervisor_heartbeats_{column}"),
            "market_supervisor_heartbeats",
            [column],
        )

    op.create_table(
        "data_freshness_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("market_timestamp", packages.database.types.UTCDateTime(timezone=True), nullable=True),
        sa.Column("received_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("processed_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("age_seconds", sa.Integer(), nullable=True),
        sa.Column("classification", sa.String(24), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "classification IN ('REAL_TIME','DELAYED','STALE','UNKNOWN')",
            name="freshness_classification_valid",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("workspace_id", "source", "symbol", "processed_at", "classification"):
        op.create_index(
            op.f(f"ix_data_freshness_observations_{column}"),
            "data_freshness_observations",
            [column],
        )
    op.create_index(
        "ix_freshness_workspace_source_processed",
        "data_freshness_observations",
        ["workspace_id", "source", "processed_at"],
    )

    op.create_table(
        "decision_signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Numeric(7, 6), nullable=False),
        sa.Column("horizon", sa.String(80), nullable=False),
        sa.Column("market_regime", sa.String(80), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("contradicting_signals", sa.JSON(), nullable=False),
        sa.Column("entry_zone", sa.JSON(), nullable=False),
        sa.Column("invalidation_rule", sa.Text(), nullable=False),
        sa.Column("risk_reference", sa.JSON(), nullable=False),
        sa.Column("freshness", sa.JSON(), nullable=False),
        sa.Column("strategy_version", sa.String(160), nullable=False),
        sa.Column("reproducibility_manifest", sa.JSON(), nullable=False),
        sa.Column("created_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('BUY','SELL','HOLD','WATCH','AVOID')",
            name="decision_signal_action_valid",
        ),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="decision_confidence_valid"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("workspace_id", "symbol", "decision", "created_at"):
        op.create_index(op.f(f"ix_decision_signals_{column}"), "decision_signals", [column])
    op.create_index(
        "ix_decision_signal_workspace_symbol_created",
        "decision_signals",
        ["workspace_id", "symbol", "created_at"],
    )

    op.create_table(
        "alert_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("severity", sa.String(24), nullable=False),
        sa.Column("dedupe_key", sa.String(240), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("cooldown_until", packages.database.types.UTCDateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("created_at", packages.database.types.UTCDateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('ACTIVE','ACKNOWLEDGED','RESOLVED')", name="alert_status_valid"),
        sa.CheckConstraint("occurrence_count >= 1", name="alert_occurrence_positive"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "dedupe_key", name="uq_alert_workspace_dedupe"),
    )
    for column in ("workspace_id", "category", "severity", "status", "created_at"):
        op.create_index(op.f(f"ix_alert_events_{column}"), "alert_events", [column])
    op.create_index(
        "ix_alert_workspace_status_created",
        "alert_events",
        ["workspace_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("alert_events")
    op.drop_table("decision_signals")
    op.drop_table("data_freshness_observations")
    op.drop_table("market_supervisor_heartbeats")
    op.drop_table("cloud_usage_ledger")
    op.drop_table("compute_job_transitions")
    op.drop_table("compute_jobs")
