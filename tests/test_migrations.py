from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from packages.core.config import get_settings


def test_clean_database_migration(tmp_path: Path, monkeypatch: object) -> None:
    database = tmp_path / "migration.db"
    monkeypatch.setenv("MIL_DATABASE_URL", f"sqlite:///{database.as_posix()}")  # type: ignore[attr-defined]
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    tables = set(inspect(create_engine(f"sqlite:///{database.as_posix()}")).get_table_names())
    assert "alembic_version" in tables
    assert "price_bars" in tables
    assert "watchlist_assets" in tables
    assert "worker_instances" in tables
    assert "reconciliation_runs" in tables
    command.check(config)
    get_settings.cache_clear()


def test_upgrade_from_v03_schema_preserves_existing_data(
    tmp_path: Path, monkeypatch: object
) -> None:
    database = tmp_path / "v03-upgrade.db"
    database_url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("MIL_DATABASE_URL", database_url)  # type: ignore[attr-defined]
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "10fdd3577a14")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO providers (
                    id, code, name, adapter_type, capabilities, configuration,
                    credential_environment_keys, is_enabled, health, created_at, updated_at
                ) VALUES (
                    :id, 'preserved', 'Preserved Provider', 'DisabledProviderAdapter',
                    '[]', '{}', '[]', 0, 'disabled', :created, :created
                )
                """
            ),
            {"id": "12345678123456781234567812345678", "created": "2026-01-01 00:00:00"},
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT code FROM providers WHERE code = 'preserved'"))
            == "preserved"
        )
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "1a52c2d25013"
    command.check(config)
    engine.dispose()
    get_settings.cache_clear()
