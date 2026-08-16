from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from packages.core.config import get_settings
from packages.database import models  # noqa: F401
from packages.database.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
migration_url = settings.migration_database_url or settings.database_url
config.set_main_option("sqlalchemy.url", migration_url.replace("%", "%%"))
target_metadata = Base.metadata

# Production executed this historical Phase-5 branch before the official
# v0.11-v0.14 line was released. These tables are retained read-only for data
# preservation, but they are intentionally not active application models.
LEGACY_PHASE5_TABLES = {
    "alert_events",
    "cloud_usage_ledger",
    "compute_job_transitions",
    "compute_jobs",
    "data_freshness_observations",
    "decision_signals",
    "market_supervisor_heartbeats",
}


def include_object(
    object_: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    """Exclude deliberately retained legacy tables from model drift."""
    return not (
        type_ == "table"
        and reflected
        and compare_to is None
        and name in LEGACY_PHASE5_TABLES
    )


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        is_sqlite = connection.dialect.name == "sqlite"
        # SQLite batch migrations rebuild tables. Keep enforcement disabled on
        # this migration-only connection so referenced tables can be replaced;
        # application connections enable it in create_database_engine().
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()
        if is_sqlite:
            violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise RuntimeError(f"SQLite foreign-key violations after migration: {violations}")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
